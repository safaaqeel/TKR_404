"""
Purpose:    Thin wrapper around the sentence-transformers embedding model
            (all-MiniLM-L6-v2). Provides a single, process-wide model instance
            so the model is loaded once and reused for every embed call, never
            reloaded per-request.
Inputs:     Raw text — either a single query string or a batch of chunk texts
            (from rag/document_loader.py::DocumentChunk.text).
Outputs:    Embedding vectors (list[float] per text) for rag/vector_store.py to
            store and rag/retriever.py to query with. Same model + settings are
            used at ingest time and query time so vectors stay comparable.
Depends on: sentence-transformers only. No project-internal imports — this
            module is foundational (§17, "Dev 3 | rag/*.py | none"), it does not
            import models/model_loader.py or anything above rag/ in the
            no-upward-imports chain (§3.3).
Called by:  models/model_loader.py, which calls get_embedding_model() once at
            app startup to warm the model before the first request (§9.1);
            rag/vector_store.py (embedding chunks to store) and
            rag/retriever.py (embedding the incoming query, §6.4).
"""

from __future__ import annotations

import logging
import threading
from typing import Sequence

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

# Cosine distance is what rag/vector_store.py's ChromaDB collection uses (§6.3),
# so embeddings are L2-normalized here to keep cosine similarity well-behaved.
_NORMALIZE_EMBEDDINGS: bool = True
_DEFAULT_BATCH_SIZE: int = 32


class EmbeddingError(Exception):
    """Raised when the embedding model fails to load or to encode text."""


class EmbeddingModel:
    """Loads all-MiniLM-L6-v2 once and exposes simple embed methods over it."""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as exc:  # noqa: BLE001 - surfaced as a structured load error
            raise EmbeddingError(
                f"Failed to load embedding model '{model_name}': {exc}"
            ) from exc
        self.embedding_dim: int = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Loaded embedding model '%s' (dim=%d)", self.model_name, self.embedding_dim
        )

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string, e.g. an incoming retrieval query (§6.4)."""
        return self.embed_texts([text])[0]

    def embed_texts(
        self, texts: Sequence[str], batch_size: int = _DEFAULT_BATCH_SIZE
    ) -> list[list[float]]:
        """
        Embed a batch of strings, e.g. chunk texts from
        rag/document_loader.py::DocumentChunk during ingestion.

        Empty/whitespace-only strings are still embedded (never silently dropped)
        so the returned list stays index-aligned with the input.
        """
        if not texts:
            return []
        try:
            vectors = self._model.encode(
                list(texts),
                batch_size=batch_size,
                normalize_embeddings=_NORMALIZE_EMBEDDINGS,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # noqa: BLE001 - structured error, never a raw traceback
            raise EmbeddingError(f"Failed to embed {len(texts)} text(s): {exc}") from exc
        return vectors.tolist()


_model_lock = threading.Lock()
_model_instance: EmbeddingModel | None = None


def get_embedding_model() -> EmbeddingModel:
    """
    Return the single process-wide EmbeddingModel instance, loading it on first
    call and reusing it thereafter. Thread-safe so concurrent requests during
    startup can't trigger a duplicate load.

    models/model_loader.py calls this once at app startup (§9.1) so the first
    real request never pays the model-load cost; callers elsewhere in rag/ can
    also call this directly and will transparently receive the same instance.
    """
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                _model_instance = EmbeddingModel()
    return _model_instance