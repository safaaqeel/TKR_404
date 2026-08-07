"""
Purpose:    Retrieves relevant knowledge-base chunks for the current plan
            step via the RAG pipeline.
Inputs:     AgentState with "plan" and "current_step_index" pointing at a
            step whose "agent" == "research_agent".
Outputs:    Mutated AgentState with state["result"][step_key] populated
            with retrieved chunks (or an empty list + confidence="low"),
            "current_step_index" advanced, "next_agent" = "decision_agent"
            (the quality gate runs before control returns to Manager).
Depends on: rag/retriever.py (Retriever — the ONLY interface into ChromaDB),
            workflows/workflow_manager.py (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent routing)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

from rag.retriever import Retriever

AGENT_NAME = "research_agent"

# Retriever wraps a persistent Chroma client — construct once per process,
# not per request.
_retriever = Retriever()


def _log(state: AgentState, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": AGENT_NAME,
            "message": message,
        }
    )


def run(state: AgentState) -> AgentState:
    _log(state, "enter")

    idx = state.get("current_step_index", 0)
    plan = state.get("plan") or []
    step = plan[idx] if idx < len(plan) else {}
    query = step.get("action") or state.get("user_query", "")
    doc_ids = step.get("doc_ids")

    # Retriever.retrieve() never raises — on internal failure it returns []
    # and logs its own warning, so this call is safe unguarded.
    chunks = _retriever.retrieve(query, k=5, doc_ids=doc_ids)

    step_key = f"step_{step.get('step', idx)}"
    result_entry: Dict[str, Any] = {"chunks": chunks}

    if not chunks:
        result_entry["confidence"] = "low"
        _log(state, f"no chunks found for query {query!r}, confidence=low")
    else:
        result_entry["confidence"] = "normal"
        _log(state, f"retrieved {len(chunks)} chunk(s) for step {step.get('step', idx)}")

    state.setdefault("result", {})[step_key] = result_entry
    state["current_step_index"] = idx + 1
    state["next_agent"] = "decision_agent"
    _log(state, "exit")
    return state