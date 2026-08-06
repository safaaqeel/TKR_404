"""
Module: app/main.py

Purpose:
    FastAPI application factory. Mounts the `frontend/` static shell,
    includes all API routes from `app/routes.py`, and initializes the
    Gemini client + embedding model exactly once at startup via
    `models/model_loader.py`. Fails fast if required environment
    variables are missing.

Inputs:
    - None directly; reads configuration via `app/config.py::get_settings()`.

Outputs:
    - `app`: the FastAPI application instance, run via
      `uvicorn app.main:app --host 0.0.0.0 --port 8000` (Master Spec §18).

Depends on:
    - app/config.py            (settings + fail-fast validation)
    - app/routes.py             (all API endpoints)
    - models/model_loader.py    (one-time Gemini + embedding init)
    - frontend/                 (static single-page shell)

Called by:
    - uvicorn (ASGI entrypoint), directly by the developer / deployment
      command. Nothing in this codebase imports app/main.py.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import ConfigError, get_settings
from app.routes import register_exception_handlers
from app.routes import router as api_router

logger = logging.getLogger("smart_automation_ai")


def _configure_logging() -> None:
    settings = get_settings()
    settings.system_log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s\t%(levelname)s\t%(name)s\t%(message)s",
        handlers=[
            logging.FileHandler(settings.system_log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook. Validates config and loads models exactly
    once, before the app accepts traffic."""
    settings = get_settings()
    _configure_logging()

    try:
        settings.validate_required()
    except ConfigError as exc:
        logger.error("Startup aborted: %s", exc)
        raise

    # Ensure the JSON store directory exists (owned by app/routes.py +
    # agents/memory_agent.py + workflows/task_pipeline.py, but the
    # directory itself is a startup-time concern).
    settings.json_store_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_persist_path.mkdir(parents=True, exist_ok=True)

    # One-time model initialization (Gemini client + embedding model).
    # models/model_loader.py is owned by another module in this repo;
    # imported lazily here so app/main.py still starts even if that
    # module is mid-development, with a clear log message if it fails.
    try:
        from models.model_loader import initialize_models

        initialize_models(settings)
        logger.info("Models initialized (Gemini client + embedding model).")
    except ImportError:
        logger.warning(
            "models/model_loader.py not available yet — skipping model init. "
            "Endpoints that require Gemini/embeddings will fail until it exists."
        )
    except Exception:
        logger.exception("Model initialization failed.")
        raise

    logger.info("Smart Automation AI backend started.")
    yield
    logger.info("Smart Automation AI backend shutting down.")


def create_app() -> FastAPI:
    """Application factory. Kept separate from the module-level `app`
    object so tests can construct fresh instances if needed."""
    application = FastAPI(
        title="Smart Automation AI",
        version="2.0",
        lifespan=lifespan,
    )

    # Local, single-user tool (Master Spec §15) — permissive CORS is
    # acceptable since the frontend is served from the same origin.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # All API endpoints live in app/routes.py (Master Spec §9.3).
    application.include_router(api_router, prefix="/api")
    register_exception_handlers(application)

    # Mount the single-page frontend shell (frontend/index.html, style.css,
    # script.js). Mounted last so it doesn't shadow /api/*.
    settings = get_settings()
    frontend_dir = settings.project_root / "frontend"
    if frontend_dir.exists():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        logger.warning("frontend/ directory not found at %s — static shell will not be served.", frontend_dir)

    return application


app = create_app()