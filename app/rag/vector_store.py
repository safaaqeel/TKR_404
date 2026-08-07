"""
Purpose:    ChromaDB client wrapper. Owns the single `documents` collection that
            is the entire searchable knowledge base (§11.1) — vector embeddings
            and their citation metadata only, never raw application state.
Inputs:     Chunk text + embedding vectors (from rag/document_loader.py and
            rag/embeddings.py) to add; a query embedding + optional filters to
            search; a doc_id to delete.
Outputs:    Raw similarity-search results (text, metadata, distance) for
            rag/retriever.py to threshold/rank/group — this module applies no
            similarity cutoff itself, that's the Retriever's job (§6.4).
Depends on: chromadb, rag/document_loader.py::DocumentChunk (sibling module in
            rag/, not an upward import). Does not read os.environ directly —
            only app/config.py does that (§12.2); the persist directory is a
            constructor parameter with a default matching .env's
            CHROMA_PERSIST_DIR.
Called by:  rag/retriever.py (the only interface agents use, §6.4);
            app/routes.py for POST /api/knowledge/upload (add) and
            DELETE /api/knowledge/{doc_id} (delete, per the three-step
            consistency rule in §11.7).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Sequence

import chromadb

from rag.document_loader import DocumentChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME: str = "documents"
DEFAULT_PERSIST_DIR: str = "database/chroma_db"


class VectorStoreError(Exception):
    """Raised when a ChromaDB add/query/delete operation fails."""


@dataclass
class SearchResult:
    """One chunk returned from a similarity search, before threshold/rank/group."""

    text: str
    metadata: dict[str, Any]
    distance: float

    @property
    def similarity(self) -> float:
        """Cosine similarity derived from Chroma's cosine distance (1 - distance)."""
        return 1.0 - self.distance


class VectorStore:
    """Thin wrapper around a persistent ChromaDB client and its `documents` collection."""

    def __init__(self, persist_dir: str = DEFAULT_PERSIST_DIR) -> None:
        self.persist_dir = persist_dir
        try:
            self._client = chromadb.PersistentClient(path=persist_dir)
            # Cosine distance per §6.3.
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:  # noqa: BLE001 - structured error, never a raw traceback
            raise VectorStoreError(
                f"Failed to initialize ChromaDB at '{persist_dir}': {exc}"
            ) from exc
        logger.info("ChromaDB collection '%s' ready at '%s'", COLLECTION_NAME, persist_dir)

    def add_chunks(
        self, chunks: Sequence[DocumentChunk], embeddings: Sequence[Sequence[float]]
    ) -> int:
        """
        Add chunks + their pre-computed embeddings to the collection.

        Args:
            chunks: DocumentChunk objects from rag/document_loader.py.
            embeddings: One embedding vector per chunk, same order, from
                rag/embeddings.py::EmbeddingModel.embed_texts().

        Returns:
            Number of chunks added.

        Raises:
            VectorStoreError: length mismatch, or the underlying Chroma call fails.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            )

        ids = [f"{chunk.doc_id}_{chunk.chunk_index}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.to_metadata() for chunk in chunks]

        try:
            self._collection.add(
                ids=ids,
                embeddings=[list(vec) for vec in embeddings],
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to add {len(chunks)} chunk(s): {exc}") from exc

        logger.info("Added %d chunk(s) to '%s'", len(chunks), COLLECTION_NAME)
        return len(chunks)

    def query(
        self,
        query_embedding: Sequence[float],
        k: int = 5,
        doc_ids: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        """
        Run a similarity search. No similarity threshold is applied here — that
        cutoff (0.35) and any grouping/citation assembly belongs to
        rag/retriever.py (§6.4).

        Args:
            query_embedding: Embedding of the search query, from the same model
                used at ingest time.
            k: Max results to return (workflows default caps this at 5, §18).
            doc_ids: Optional allow-list to restrict the search to specific docs.

        Returns:
            SearchResult list ordered by ascending distance (best match first).
            Empty list if the collection has no matches or the query fails —
            callers should treat an empty list as "no results", not an error.
        """
        where = {"doc_id": {"$in": list(doc_ids)}} if doc_ids else None
        try:
            raw = self._collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=k,
                where=where,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector store query failed: %s", exc)
            return []

        documents = raw.get("documents") or [[]]
        metadatas = raw.get("metadatas") or [[]]
        distances = raw.get("distances") or [[]]

        results = [
            SearchResult(text=doc, metadata=meta, distance=dist)
            for doc, meta, dist in zip(documents[0], metadatas[0], distances[0])
        ]
        return results

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """
        Remove every chunk belonging to doc_id. This is step 1 of the three-step
        document deletion in §11.7 — the caller (app/routes.py) is still
        responsible for deleting the source file and the user_data.json index
        entry, and for reporting a partial failure explicitly if any step fails.

        Returns:
            True if the delete call succeeded (even if zero chunks matched),
            False if the underlying Chroma call raised.
        """
        try:
            self._collection.delete(where={"doc_id": doc_id})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete doc_id '%s': %s", doc_id, exc)
            return False
        logger.info("Deleted all chunks for doc_id '%s'", doc_id)
        return True

    def count(self) -> int:
        """Total chunk count currently stored, mainly for health checks/tests."""
        try:
            return self._collection.count()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to count '%s': %s", COLLECTION_NAME, exc)
            return 0


_store_lock = threading.Lock()
_store_instance: VectorStore | None = None


def delete_document(doc_id: str) -> bool:
    """Module-level convenience wrapper around the singleton VectorStore's
    delete_by_doc_id(), for callers (app/routes.py DELETE /api/knowledge/{id})
    that don't hold their own VectorStore instance.

    Returns True if the delete call succeeded (even if zero chunks matched).
    """
    return get_vector_store().delete_by_doc_id(doc_id)


def get_vector_store(persist_dir: str = DEFAULT_PERSIST_DIR) -> VectorStore:
    """
    Return the single process-wide VectorStore instance, creating it on first
    call. Thread-safe. Mirrors rag/embeddings.py::get_embedding_model() so both
    the model and the Chroma client are initialized once, not per-request.
    """
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = VectorStore(persist_dir=persist_dir)
    return _store_instance