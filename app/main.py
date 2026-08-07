from __future__ import annotations

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# --- Make bare top-level imports resolve -----------------------------------
# Several existing modules (app/rag/*.py, app/agents_pipeline/*.py) import
# their siblings as bare top-level packages, e.g.:
#     from rag.embeddings import ...      (in app/rag/retriever.py)
#     from tools import calendar_tool     (in app/agents_pipeline/automation_agent.py)
#     from models.model_loader import ... (in app/agents_pipeline/decision_agent.py)
# For those to import successfully, app/ itself (not just the project root)
# must be on sys.path. Project root is added automatically when you run
# `uvicorn app.main:app` from TKR_404/, but app/ is not — so we add it here,
# once, before anything below tries to import those packages.
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import router as legacy_router, register_exception_handlers
from app.api import (
    dashboard,
    reports,
    knowledge,
    settings as settings_router,
    simulator,
    schemes,
    competitor,
    agents,
    checkin,
)

logger = logging.getLogger("smart_automation_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("========== STARTUP ==========")
    print("Backend starting...")

    # Fail fast on missing required config (GEMINI_API_KEY etc.)
    get_settings().validate_required()

    # Load ML/LLM singletons once at startup, not per-request.
    try:
        from app.models import model_loader
        model_loader.initialize()
        print("model_loader initialized (Gemini + embeddings + risk model).")
    except Exception as exc:  # noqa: BLE001
        # Don't crash the whole app if e.g. the risk model .pkl files aren't
        # trained yet — routes that depend on them should degrade gracefully.
        print(f"WARNING: model_loader.initialize() failed: {exc}")

    print("Backend starting complete.")
    yield
    print("Backend shutting down...")


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

    # Standard error-envelope handler for ApiError (defined in app/routes.py).
    register_exception_handlers(app)

    # --- Mount every API router BEFORE the static-file catch-all below. ---
    # Order matters: StaticFiles is mounted at "/" and will swallow any
    # request that isn't matched by a route registered before it.

    # legacy_router (app/routes.py) owns /api/tasks, /api/knowledge/upload,
    # /api/knowledge, /api/memory — mounted under /api per its own docstring.
    # NOTE: routes.py's GET /settings was removed to avoid colliding with
    # app/api/settings.py's GET "" (see app/routes.py diff).
    app.include_router(legacy_router, prefix="/api")

    # New domain routers already declare their own /api/... prefixes.
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(knowledge.router)
    app.include_router(settings_router.router)
    app.include_router(simulator.router)
    app.include_router(schemes.router)
    app.include_router(competitor.router)
    app.include_router(agents.router)
    app.include_router(checkin.router)

    frontend_dir = Path(__file__).resolve().parent / "frontend"

    print("===================================")
    print("Frontend directory:", frontend_dir)
    print("Exists:", frontend_dir.exists())
    print("Index exists:", (frontend_dir / "index.html").exists())
    print("===================================")

    if frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )
        print("Frontend mounted.")
    else:
        print("Frontend NOT found!")

    return app


app = create_app()