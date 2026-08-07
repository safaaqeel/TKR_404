"""
Single place where every expensive resource is loaded ONCE at app boot:
- Gemini client
- ChromaDB collection handle
- Sentence-transformer embedding model
- ML models (XGBoost, Isolation Forest, Prophet)

Import and call load_all_resources() from main.py's startup event / lifespan.
Everything downstream (agents, services, ml modules) should receive these
via dependency injection or a shared app.state object - never re-instantiate
a model or client inside a request handler.
"""
import logging

logger = logging.getLogger("smart_automation_ai.startup")


class AppResources:
    """Holds every singleton resource the app needs, attached to app.state."""
    gemini_client = None
    chroma_collection = None
    embedding_model = None
    xgboost_risk_model = None
    isolation_forest_model = None
    prophet_models_cache: dict = {}


resources = AppResources()


def load_all_resources():
    logger.info("Loading application resources (models, clients, embeddings)...")

    # from app.services.gemini_service import build_gemini_client
    # resources.gemini_client = build_gemini_client()

    # from app.rag.vector_store import get_chroma_collection
    # resources.chroma_collection = get_chroma_collection()

    # from sentence_transformers import SentenceTransformer
    # resources.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    # import joblib
    # resources.xgboost_risk_model = joblib.load("app/models/xgboost_model.pkl")

    logger.info("Resource loading complete.")
    return resources
