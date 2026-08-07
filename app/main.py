"""
Module: app/main.py

Purpose:
FastAPI application entrypoint.

- Initializes logging.
- Validates configuration.
- Loads ML models exactly once.
- Registers all API routers.
- Serves the frontend from app/frontend/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import ConfigError, get_settings

# ---------------------------------------------------
# Logging
# ---------------------------------------------------

logger = logging.getLogger("smart_automation_ai")


def configure_logging():
    settings = get_settings()

    settings.system_log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(settings.system_log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# ---------------------------------------------------
# Lifespan
# ---------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()

    configure_logging()

    try:
        settings.validate_required()
    except ConfigError as e:
        logger.error(e)
        raise

    settings.json_store_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_persist_path.mkdir(parents=True, exist_ok=True)

    try:
        from app.models.model_loader import initialize_models

        initialize_models(settings)

        logger.info("Models initialized successfully.")

    except ImportError:

        logger.warning(
            "model_loader.py not available. "
            "Continuing without AI models."
        )

    except Exception:

        logger.exception("Model initialization failed.")

        raise

    logger.info("Smart Automation AI backend started.")

    yield

    logger.info("Backend shutdown.")


# ---------------------------------------------------
# App Factory
# ---------------------------------------------------

def create_app() -> FastAPI:

    app = FastAPI(
        title="Smart Automation AI",
        version="2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # ------------------------------------------------
    # Register API routers
    # ------------------------------------------------

    try:

        from app.api.dashboard import router as dashboard_router
        app.include_router(dashboard_router, prefix="/api")

    except Exception:
        logger.exception("dashboard router failed")

    try:

        from app.api.simulator import router as simulator_router
        app.include_router(simulator_router, prefix="/api")

    except Exception:
        logger.exception("simulator router failed")

    try:

        from app.api.knowledge import router as knowledge_router
        app.include_router(knowledge_router, prefix="/api")

    except Exception:
        logger.exception("knowledge router failed")

    try:

        from app.api.settings import router as settings_router
        app.include_router(settings_router, prefix="/api")

    except Exception:
        logger.exception("settings router failed")

    try:

        from app.api.reports import router as reports_router
        app.include_router(reports_router, prefix="/api")

    except Exception:
        logger.exception("reports router failed")

    try:

        from app.api.schemes import router as schemes_router
        app.include_router(schemes_router, prefix="/api")

    except Exception:
        logger.exception("schemes router failed")

    try:

        from app.api.competitor import router as competitor_router
        app.include_router(competitor_router, prefix="/api")

    except Exception:
        logger.exception("competitor router failed")

    try:

        from app.api.agents import router as agents_router
        app.include_router(agents_router, prefix="/api")

    except Exception:
        logger.exception("agents router failed")

    try:

        from app.api.checkin import router as checkin_router
        app.include_router(checkin_router, prefix="/api")

    except Exception:
        logger.exception("checkin router failed")

    # ------------------------------------------------
    # Frontend
    # ------------------------------------------------

    frontend_dir = Path(__file__).resolve().parent / "frontend"

    if frontend_dir.exists():

        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )

        logger.info("Frontend mounted successfully.")

    else:

        logger.warning(
            f"Frontend directory not found: {frontend_dir}"
        )

    return app


app = create_app()