"""
Module: app/routes.py

Purpose:
    ALL API endpoints for Smart Automation AI live in this single file
    (Master Spec §9.3), split by comment headers rather than by file.
    Validates requests with Pydantic and delegates business logic to
    `workflows/task_pipeline.py`, `rag/*`, and `agents/memory_agent.py`.
    No business logic lives here — this is a thin HTTP layer only
    (Master Spec §3.2).

Inputs:
    - HTTP requests (JSON bodies, multipart file uploads, path/query params).

Outputs:
    - JSON responses. All errors use the standard envelope:
      `{ "error": { "code", "message", "detail" } }` (Master Spec §9.3).

Depends on:
    - app/config.py                  (settings singleton)
    - workflows/task_pipeline.py     (task lifecycle: create/get/stream/confirm/cancel/list)
    - rag/document_loader.py         (ingest uploaded documents)
    - rag/vector_store.py            (delete document vectors)
    - agents/memory_agent.py         (list/forget learned preferences)
    - database/user_data.json        (settings + knowledge-base index, read/written directly here —
                                       this is the ONE file user_data.json's schema says app/routes.py owns)

Called by:
    - app/main.py (mounted under the "/api" prefix)
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger("smart_automation_ai.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# Standard error envelope
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Raised by handlers to produce the standard error envelope."""

    def __init__(self, status_code: int, code: str, message: str, detail: Optional[str] = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


def _error_response(exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
    )


# ---------------------------------------------------------------------------
# database/user_data.json helpers (single writer: app/routes.py, per §11.2)
# ---------------------------------------------------------------------------

_DEFAULT_USER_DATA = {
    "sessions": {},
    "settings": {
        "digest_frequency": "weekly",
        "notification_channel": "email",
        "theme": "light",
    },
    "knowledge_base_index": {},  # doc_id -> {filename, status, chunk_count, source_type, ingested_at}
}


def _read_user_data() -> dict:
    settings = get_settings()
    path = settings.user_data_path
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULT_USER_DATA, indent=2), encoding="utf-8")
        return json.loads(json.dumps(_DEFAULT_USER_DATA))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("user_data.json is corrupt: %s", exc)
        raise ApiError(500, "user_data_corrupt", "The user data store is corrupt.", str(exc))


def _write_user_data(data: dict) -> None:
    settings = get_settings()
    path = settings.user_data_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class CreateTaskRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="Natural-language goal for the task.")
    context: dict = Field(default_factory=dict, description="Optional file_ids/doc_ids/extra context.")


class SettingsUpdateRequest(BaseModel):
    digest_frequency: Optional[str] = None
    notification_channel: Optional[str] = None
    theme: Optional[str] = None


# ===========================================================================
# TASKS — POST/GET /api/tasks, GET stream, POST confirm/cancel
# ===========================================================================

@router.post("/tasks")
async def create_task(payload: CreateTaskRequest):
    """Create + start a task. Delegates to workflows/task_pipeline.py."""
    try:
        from workflows.task_pipeline import create_task as pipeline_create_task
    except ImportError as exc:
        raise ApiError(503, "task_pipeline_unavailable", "Task pipeline is not available.", str(exc))

    try:
        state = await pipeline_create_task(goal=payload.goal, context=payload.context)
    except Exception as exc:  # noqa: BLE001 - surfaced via standard envelope
        logger.exception("Failed to create task")
        raise ApiError(500, "task_creation_failed", "Could not create the task.", str(exc))

    return state


@router.get("/tasks")
async def list_tasks():
    """List past tasks, read directly from database/task_history.json."""
    settings = get_settings()
    path = settings.task_history_path
    if not path.exists():
        return {"tasks": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(500, "task_history_corrupt", "The task history store is corrupt.", str(exc))
    return {"tasks": data.get("tasks", [])}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get current task state."""
    try:
        from workflows.task_pipeline import get_task as pipeline_get_task
    except ImportError as exc:
        raise ApiError(503, "task_pipeline_unavailable", "Task pipeline is not available.", str(exc))

    state = await pipeline_get_task(task_id)
    if state is None:
        raise ApiError(404, "task_not_found", f"No task with id {task_id!r}.")
    return state


@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE live progress for a running task."""
    try:
        from workflows.task_pipeline import stream_task as pipeline_stream_task
    except ImportError as exc:
        raise ApiError(503, "task_pipeline_unavailable", "Task pipeline is not available.", str(exc))

    async def event_generator():
        try:
            async for event in pipeline_stream_task(task_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE stream failed for task %s", task_id)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/tasks/{task_id}/confirm")
async def confirm_task(task_id: str):
    """Approve a high-risk plan step, unblocking the Automation Agent."""
    try:
        from workflows.task_pipeline import confirm_task as pipeline_confirm_task
    except ImportError as exc:
        raise ApiError(503, "task_pipeline_unavailable", "Task pipeline is not available.", str(exc))

    try:
        state = await pipeline_confirm_task(task_id)
    except KeyError:
        raise ApiError(404, "task_not_found", f"No task with id {task_id!r}.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to confirm task %s", task_id)
        raise ApiError(500, "task_confirm_failed", "Could not confirm the task.", str(exc))
    return state


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    try:
        from workflows.task_pipeline import cancel_task as pipeline_cancel_task
    except ImportError as exc:
        raise ApiError(503, "task_pipeline_unavailable", "Task pipeline is not available.", str(exc))

    try:
        state = await pipeline_cancel_task(task_id)
    except KeyError:
        raise ApiError(404, "task_not_found", f"No task with id {task_id!r}.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to cancel task %s", task_id)
        raise ApiError(500, "task_cancel_failed", "Could not cancel the task.", str(exc))
    return state


# ===========================================================================
# KNOWLEDGE — upload / list / delete documents
# ===========================================================================

@router.post("/knowledge/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload + ingest a document. Server-side validation of extension and
    size is authoritative (Master Spec §15); client-side is convenience only."""
    settings = get_settings()

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.allowed_upload_extensions:
        raise ApiError(
            400,
            "unsupported_file_type",
            f"Unsupported file type {suffix!r}.",
            f"Allowed extensions: {', '.join(settings.allowed_upload_extensions)}",
        )

    upload_dir = settings.project_root / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    dest_path = upload_dir / f"{doc_id}{suffix}"

    size = 0
    with dest_path.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.upload_max_bytes:
                out_file.close()
                dest_path.unlink(missing_ok=True)
                raise ApiError(
                    413,
                    "file_too_large",
                    "Uploaded file exceeds the 25MB limit.",
                    f"received {size} bytes",
                )
            out_file.write(chunk)

    try:
        from rag.document_loader import ingest as rag_ingest
    except ImportError as exc:
        dest_path.unlink(missing_ok=True)
        raise ApiError(503, "rag_unavailable", "Document ingestion is not available.", str(exc))

    try:
        ingest_result = rag_ingest(str(dest_path), doc_id=doc_id, source_type=suffix.lstrip("."))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ingestion failed for %s", dest_path)
        raise ApiError(500, "ingestion_failed", "Failed to ingest the uploaded document.", str(exc))

    data = _read_user_data()
    data["knowledge_base_index"][doc_id] = {
        "filename": file.filename,
        "status": "indexed",
        "chunk_count": ingest_result.get("chunk_count", 0) if isinstance(ingest_result, dict) else 0,
        "source_type": suffix.lstrip("."),
        "ingested_at": _now_iso(),
    }
    _write_user_data(data)

    return {"doc_id": doc_id, "filename": file.filename, **data["knowledge_base_index"][doc_id]}


@router.get("/knowledge")
async def list_knowledge():
    """List indexed documents, read from database/user_data.json index metadata."""
    data = _read_user_data()
    return {"documents": data.get("knowledge_base_index", {})}


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str):
    """Remove a document: Chroma vectors + source file + index entry.
    Per Master Spec §11.7, this is a three-step operation — all three must
    succeed or the operation reports a partial failure explicitly."""
    data = _read_user_data()
    entry = data.get("knowledge_base_index", {}).get(doc_id)
    if entry is None:
        raise ApiError(404, "document_not_found", f"No document with id {doc_id!r}.")

    failures: list[str] = []

    try:
        from rag.vector_store import delete_document as vector_delete_document

        vector_delete_document(doc_id)
    except ImportError:
        failures.append("vector_store_unavailable")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to delete vectors for %s", doc_id)
        failures.append(f"vector_delete_failed: {exc}")

    for base in ("data/documents", "data/uploads"):
        settings = get_settings()
        candidates = list((settings.project_root / base).glob(f"**/{doc_id}*"))
        for path in candidates:
            try:
                path.unlink()
            except OSError as exc:
                failures.append(f"file_delete_failed: {exc}")

    del data["knowledge_base_index"][doc_id]
    _write_user_data(data)

    if failures:
        raise ApiError(
            207,
            "partial_delete",
            f"Document {doc_id!r} was partially removed.",
            "; ".join(failures),
        )
    return {"doc_id": doc_id, "deleted": True}


# ===========================================================================
# MEMORY — list / forget learned preferences (owned by agents/memory_agent.py)
# ===========================================================================

@router.get("/memory")
async def list_memory():
    """List learned preferences via agents/memory_agent.py's read helper."""
    try:
        from agents.memory_agent import list_memories
    except ImportError as exc:
        raise ApiError(503, "memory_agent_unavailable", "Memory agent is not available.", str(exc))
    return {"memories": list_memories()}


@router.delete("/memory/{memory_id}")
async def forget_memory(memory_id: str):
    """Forget one memory entry."""
    try:
        from agents.memory_agent import forget_memory as agent_forget_memory
    except ImportError as exc:
        raise ApiError(503, "memory_agent_unavailable", "Memory agent is not available.", str(exc))

    removed = agent_forget_memory(memory_id)
    if not removed:
        raise ApiError(404, "memory_not_found", f"No memory with id {memory_id!r}.")
    return {"memory_id": memory_id, "deleted": True}


@router.delete("/memory")
async def forget_all_memory():
    """Forget everything the Memory Agent has learned."""
    try:
        from agents.memory_agent import forget_all_memories
    except ImportError as exc:
        raise ApiError(503, "memory_agent_unavailable", "Memory agent is not available.", str(exc))

    count = forget_all_memories()
    return {"deleted_count": count}


# ===========================================================================
# SETTINGS — read/update (database/user_data.json)
# ===========================================================================

@router.get("/settings")
async def get_settings_endpoint():
    data = _read_user_data()
    return data.get("settings", {})


@router.put("/settings")
async def update_settings(payload: SettingsUpdateRequest):
    data = _read_user_data()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    data.setdefault("settings", {}).update(updates)
    _write_user_data(data)
    return data["settings"]


# ---------------------------------------------------------------------------
# Exception handler registration helper (wired in app/main.py's app factory
# via FastAPI's default exception propagation — ApiError is translated here)
# ---------------------------------------------------------------------------

from fastapi.requests import Request  # noqa: E402  (kept near usage for clarity)


def register_exception_handlers(app) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError):
        return _error_response(exc)


# NOTE: app/main.py should call `register_exception_handlers(app)` after
# `create_app()` if it wants ApiError to render as the standard envelope
# instead of FastAPI's default 500. Kept as an explicit opt-in call here
# rather than import-time side effects.