"""
Purpose:    The only module in the codebase with write access to
            database/conversation_memory.json. Exposes a read helper used
            by Manager Agent at the start of every run (and by GET
            /api/memory), and owns the write path used at end-of-run.
Inputs:     run(state) expects a completed/failed AgentState whose
            state["result"]["memory_candidates"] may contain candidate
            facts/preferences: {"type": "fact"|"preference", "content": str,
            "user_confirmed": bool}.
Outputs:    Mutated AgentState with "next_agent" = None (terminal node);
            side effect of updating database/conversation_memory.json. A
            candidate is only persisted as a durable entry once it has
            either been explicitly confirmed by the user, or observed on
            two separate runs (tracked via an internal "pending" list).
Depends on: database/conversation_memory.json, workflows/workflow_manager.py
            (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent
            routing); read_memory_context() is also called directly by
            agents/manager_agent.py and by GET /api/memory in app/routes.py;
            forget() is called by DELETE /api/memory[/{id}] in app/routes.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

AGENT_NAME = "memory_agent"
MEMORY_PATH = Path("database/conversation_memory.json")


def _log(state: AgentState, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": AGENT_NAME,
            "message": message,
        }
    )


def _load() -> Dict[str, List[Dict[str, Any]]]:
    if not MEMORY_PATH.exists():
        return {"entries": [], "pending": []}
    with MEMORY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("entries", [])
    data.setdefault("pending", [])
    return data


def _save(data: Dict[str, List[Dict[str, Any]]]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_memory_context(task_id: str) -> Dict[str, Any]:
    """Read-only helper used by Manager Agent (and GET /api/memory)."""
    entries = _load()["entries"]
    return {
        "facts": [e for e in entries if e.get("type") == "fact"],
        "preferences": [e for e in entries if e.get("type") == "preference"],
    }


def forget(memory_id: Optional[str] = None) -> None:
    """Used by DELETE /api/memory/{id} (single) and DELETE /api/memory (all)."""
    if memory_id is None:
        _save({"entries": [], "pending": []})
        return
    data = _load()
    data["entries"] = [e for e in data["entries"] if e.get("memory_id") != memory_id]
    _save(data)


def _promote(data: Dict[str, List[Dict[str, Any]]], candidate: Dict[str, Any], now: str) -> None:
    data["entries"].append(
        {
            "memory_id": str(uuid.uuid4()),
            "type": candidate["type"],
            "content": candidate["content"],
            "confidence": 1.0,
            "first_seen": now,
            "last_confirmed": now,
        }
    )


def _upsert_candidate(data: Dict[str, List[Dict[str, Any]]], candidate: Dict[str, Any], now: str) -> None:
    confirmed = bool(candidate.get("user_confirmed", False))

    if confirmed:
        existing = next(
            (e for e in data["entries"] if e["type"] == candidate["type"] and e["content"] == candidate["content"]),
            None,
        )
        if existing:
            existing["confidence"] = 1.0
            existing["last_confirmed"] = now
        else:
            _promote(data, candidate, now)
        data["pending"] = [
            p for p in data["pending"] if not (p["type"] == candidate["type"] and p["content"] == candidate["content"])
        ]
        return

    # Not explicitly confirmed: only persist once seen on a second run.
    pending_match = next(
        (p for p in data["pending"] if p["type"] == candidate["type"] and p["content"] == candidate["content"]),
        None,
    )
    if pending_match:
        data["pending"].remove(pending_match)
        _promote(data, candidate, now)
    else:
        data["pending"].append({"type": candidate["type"], "content": candidate["content"], "first_seen": now})


def run(state: AgentState) -> AgentState:
    _log(state, "enter")

    candidates: List[Dict[str, Any]] = state.get("result", {}).get("memory_candidates", [])
    if candidates:
        now = datetime.now(timezone.utc).isoformat()
        data = _load()
        for candidate in candidates:
            _upsert_candidate(data, candidate, now)
        _save(data)
        _log(state, f"processed {len(candidates)} memory candidate(s)")
    else:
        _log(state, "no memory candidates this run")

    state["next_agent"] = None
    _log(state, "exit")
    return state