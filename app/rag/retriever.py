"""
Purpose:    The only interface agents use to query the knowledge base (§3.2,
            §6.4). Embeds the incoming query with the same model used at ingest,
            searches rag/vector_store.py, drops low-similarity results, and
            groups the surviving chunks by source document for citation.
Inputs:     A natural-language query string, an optional result cap `k`
            (workflows default to k=5, §18), and an optional doc_ids allow-list.
Outputs:    list[RetrievedDocument] — chunks grouped by their source document,
            each chunk carrying similarity + citation metadata (filename,
            page_number, chunk_index). Empty list on no matches or any failure —
            retrieval never raises out to a caller.
Depends on: rag/embeddings.py (get_embedding_model), rag/vector_store.py
            (get_vector_store) — both sibling modules within rag/, not upward
            imports (§3.3).
Called by:  agents/research_agent.py, via Retriever.retrieve() (§5.3). No other
            module queries ChromaDB directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from rag.embeddings import EmbeddingError, EmbeddingModel, get_embedding_model
from rag.vector_store import SearchResult, VectorStore, get_vector_store

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD: float = 0.35
DEFAULT_K: int = 5


@dataclass
class RetrievedChunk:
    """One matching chunk, ready to cite."""

    text: str
    chunk_index: int
    page_number: int | None
    similarity: float


@dataclass
class RetrievedDocument:
    """One source document with all of its matching chunks, best match first."""

    doc_id: str
    filename: str
    source_type: str
    chunks: list[RetrievedChunk] = field(default_factory=list)

    @property
    def best_similarity(self) -> float:
        return max((c.similarity for c in self.chunks), default=0.0)


class Retriever:
    """Embeds a query, searches the vector store, filters and groups results."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self._vector_store = vector_store or get_vector_store()
        self._embedding_model = embedding_model or get_embedding_model()

    def retrieve(
        self,
        query: str,
        k: int = DEFAULT_K,
        doc_ids: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """
        Retrieve relevant chunks for `query`, grouped by source document.

        Never raises: any embedding or vector-store failure is logged as a
        warning and results in an empty list, per §6.4 — a retrieval problem
        must not crash the calling agent's task.

        Args:
            query: Natural-language search text (e.g. the current plan step).
            k: Max chunks to consider before grouping (not max documents).
            doc_ids: Optional allow-list to restrict the search to specific docs.

        Returns:
            RetrievedDocument list, ordered by each document's best chunk
            similarity (descending). Empty list if nothing scores above
            SIMILARITY_THRESHOLD, or if retrieval failed.
        """
        try:
            return self._retrieve(query, k=k, doc_ids=doc_ids)
        except Exception as exc:  # noqa: BLE001 - last-resort guard, retrieval must never crash a task
            logger.warning("Retrieval failed for query %r: %s", query, exc)
            return []

    def _retrieve(
        self,
        query: str,
        k: int,
        doc_ids: list[str] | None,
    ) -> list[RetrievedDocument]:
        if not query or not query.strip():
            return []

        try:
            query_embedding = self._embedding_model.embed_text(query)
        except EmbeddingError as exc:
            logger.warning("Failed to embed query %r: %s", query, exc)
            return []

        results: list[SearchResult] = self._vector_store.query(
            query_embedding, k=k, doc_ids=doc_ids
        )

        filtered = [r for r in results if r.similarity >= SIMILARITY_THRESHOLD]
        if not filtered:
            logger.info(
                "No chunks above similarity %.2f for query %r", SIMILARITY_THRESHOLD, query
            )
            return []

        documents: dict[str, RetrievedDocument] = {}
        for result in filtered:
            meta = result.metadata
            doc_id = meta.get("doc_id", "")
            if doc_id not in documents:
                documents[doc_id] = RetrievedDocument(
                    doc_id=doc_id,
                    filename=meta.get("filename", ""),
                    source_type=meta.get("source_type", ""),
                )
            documents[doc_id].chunks.append(
                RetrievedChunk(
                    text=result.text,
                    chunk_index=meta.get("chunk_index", 0),
                    page_number=meta.get("page_number"),
                    similarity=result.similarity,
                )
            )

        for doc in documents.values():
            doc.chunks.sort(key=lambda c: c.similarity, reverse=True)

        ranked = sorted(documents.values(), key=lambda d: d.best_similarity, reverse=True)
        logger.info(
            "Query %r -> %d chunk(s) across %d document(s)",
            query,
            len(filtered),
            len(ranked),
        )
        return ranked


_default_retriever: Retriever | None = None


def _get_default_retriever() -> Retriever:
    """Process-wide singleton Retriever, lazily constructed on first use."""
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = Retriever()
    return _default_retriever


def retrieve_relevant_documents(
    query: str,
    top_k: int = DEFAULT_K,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    """Module-level convenience wrapper around Retriever.retrieve(), for
    callers (app/api/knowledge.py, agents_pipeline/research_agent.py) that
    just want plain JSON-serializable dicts rather than the dataclasses.

    Never raises (Retriever.retrieve() already fails closed to []).
    """
    documents = _get_default_retriever().retrieve(query, k=top_k, doc_ids=doc_ids)
    return [
        {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "source_type": doc.source_type,
            "best_similarity": doc.best_similarity,
            "chunks": [
                {
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "similarity": chunk.similarity,
                }
                for chunk in doc.chunks
            ],
        }
        for doc in documents
    ]