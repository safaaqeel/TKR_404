"""
Purpose: Initialize the Gemini LLM client and the Sentence-Transformers
         embedding model ONCE at application startup, and expose them
         as module-level singletons for the rest of the app to import.
Inputs: GEMINI_API_KEY (via app/config.py Settings)
Outputs: get_llm_client() -> genai.GenerativeModel
         get_embedding_model() -> SentenceTransformer
Depends on: app/config.py (Settings), google-generativeai, sentence-transformers
Called by: app/main.py (at startup), rag/embeddings.py, agents/*_agent.py (LLM calls)
"""

import logging

import google.generativeai as genai
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_MODEL_NAME = "gemini-1.5-pro"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_llm_client = None
_embedding_model = None
_initialized = False


def initialize() -> None:
    """Initialize Gemini + embedding model exactly once. Call at app startup."""
    global _llm_client, _embedding_model, _initialized

    if _initialized:
        logger.info("model_loader.initialize() called again — skipping, already initialized.")
        return

    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. The app must fail fast at startup "
            "if required env vars are missing (see spec §9.1)."
        )

    logger.info("Initializing Gemini client with model=%s", GEMINI_MODEL_NAME)
    genai.configure(api_key=settings.GEMINI_API_KEY)
    _llm_client = genai.GenerativeModel(GEMINI_MODEL_NAME)

    logger.info("Loading embedding model=%s", EMBEDDING_MODEL_NAME)
    _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    _initialized = True
    logger.info("model_loader initialization complete.")


def get_llm_client():
    if _llm_client is None:
        raise RuntimeError(
            "LLM client not initialized. Call model_loader.initialize() "
            "at app startup before requesting the client."
        )
    return _llm_client


def get_embedding_model():
    if _embedding_model is None:
        raise RuntimeError(
            "Embedding model not initialized. Call model_loader.initialize() "
            "at app startup before requesting the model."
        )
    return _embedding_model


def is_initialized() -> bool:
    return _initialized