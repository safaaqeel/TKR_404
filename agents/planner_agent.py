"""
Purpose:    Converts a natural-language goal (state["user_query"]) into a
            structured, ordered plan the rest of the graph can execute.
Inputs:     AgentState with "user_query" and (optionally) "context".
Outputs:    Mutated AgentState with "plan" (list[dict] matching the §4
            shape: step/agent/action/risk/depends_on), "current_step_index"
            = 0, and "next_agent" = "manager_agent". On unrecoverable
            failure: "status" = "awaiting_review" with "error_detail" set.
Depends on: models/prompt_templates.py (PLANNER_PROMPT), models/model_loader.py
            (Gemini client, initialized once at startup), workflows/workflow_manager.py
            (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent routing)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

from models.model_loader import get_llm_client
from models.prompt_templates import PLANNER_PROMPT

AGENT_NAME = "planner_agent"
REQUIRED_STEP_KEYS = {"step", "agent", "action", "risk", "depends_on"}


def _log(state: AgentState, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": AGENT_NAME,
            "message": message,
        }
    )


def _strip_code_fence(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _parse_plan(raw_text: str) -> Optional[List[dict]]:
    """Best-effort JSON parse + shape validation. Returns None on failure."""
    try:
        plan = json.loads(_strip_code_fence(raw_text))
    except json.JSONDecodeError:
        return None

    if not isinstance(plan, list) or not plan:
        return None

    for item in plan:
        if not isinstance(item, dict) or not REQUIRED_STEP_KEYS.issubset(item.keys()):
            return None
        if item.get("risk") not in ("low", "high"):
            return None

    return plan


def _request_plan(client, user_query: str, context: dict) -> str:
    prompt = PLANNER_PROMPT.format(user_query=user_query, context=json.dumps(context, default=str))
    return client.generate(prompt)


def run(state: AgentState) -> AgentState:
    _log(state, "enter")

    client = get_llm_client()
    user_query = state.get("user_query", "")
    context = state.get("context", {})

    raw = _request_plan(client, user_query, context)
    plan = _parse_plan(raw)

    if plan is None:
        # One automatic re-prompt, per spec, before giving up.
        _log(state, "malformed plan JSON, re-prompting once")
        raw = _request_plan(client, user_query, context)
        plan = _parse_plan(raw)

    if plan is None:
        state["status"] = "awaiting_review"
        state["error_detail"] = (
            "Could not produce a valid plan from the goal as stated. "
            "Please clarify or narrow the request."
        )
        state["next_agent"] = None
        _log(state, "plan still malformed after retry -> awaiting_review with clarification request")
        _log(state, "exit")
        return state

    state["plan"] = plan
    state["current_step_index"] = 0
    state["status"] = "running"
    state["next_agent"] = "manager_agent"
    _log(state, f"plan created with {len(plan)} step(s)")
    _log(state, "exit")
    return state