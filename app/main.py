from __future__ import annotations

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

logger = logging.getLogger("smart_automation_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("========== STARTUP ==========")
    print("Backend starting...")
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