"""
Purpose:    Thin dispatcher that executes side-effecting actions (email,
            files, webhooks, calendar, notifications) for plan steps whose
            "agent" == "automation_agent". Contains no automation logic
            itself — every action is delegated to a named function in tools/.
Inputs:     AgentState with "plan"/"current_step_index" pointing at an
            automation step, and "status" (must be "confirmed" for any
            risk: high step — enforced here independently of Manager Agent's
            own gate, per §5.5).
Outputs:    Mutated AgentState with state["result"][step_key] recording the
            tool call outcome (or a structured error), "next_agent" =
            "manager_agent".
Depends on: tools/email_tool.py, tools/calendar_tool.py, tools/file_tool.py,
            tools/web_tool.py, tools/notification_tool.py,
            workflows/workflow_manager.py (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent routing)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

from tools import calendar_tool, email_tool, file_tool, notification_tool, web_tool

AGENT_NAME = "automation_agent"

# Maps a step's "action_type" to the tool function that handles it. Adding a
# new automation capability (e.g. Slack posting) means adding a file to
# tools/ and one entry here — no other file changes, per §19.
_DISPATCH: Dict[str, Callable[..., Any]] = {
    "send_email": email_tool.send,
    "create_event": calendar_tool.create_event,
    "write_file": file_tool.write,
    "read_file": file_tool.read,
    "webhook": web_tool.post,
    "notify": notification_tool.notify,
}


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
    step_key = f"step_{step.get('step', idx)}"

    if step.get("risk") == "high" and state.get("status") != "confirmed":
        # Manager Agent should already have gated this before routing here,
        # but the dispatcher enforces it independently as a hard safety
        # check — no high-risk action ever fires without confirmation.
        state["status"] = "awaiting_review"
        state["next_agent"] = None
        _log(state, f"blocked high-risk step {step.get('step')} pending confirmation")
        _log(state, "exit")
        return state

    action_type = step.get("action_type")
    tool_fn = _DISPATCH.get(action_type)

    if tool_fn is None:
        state.setdefault("result", {})[step_key] = {
            "error": True,
            "message": f"Unknown automation action_type: {action_type!r}",
        }
        _log(state, f"unknown action_type {action_type!r}")
    else:
        try:
            outcome = tool_fn(**step.get("action_args", {}))
            state.setdefault("result", {})[step_key] = {"success": True, "outcome": outcome}
            _log(state, f"dispatched {action_type} via {tool_fn.__module__}.{tool_fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - tools raise varied, tool-specific exceptions
            state.setdefault("result", {})[step_key] = {"error": True, "message": str(exc)}
            _log(state, f"{action_type} failed: {exc}")

    state["current_step_index"] = idx + 1
    state["status"] = "running"
    # Route through the quality gate before handing back to Manager, per
    # §5 of the governing spec (Decision reviews every completed step).
    state["next_agent"] = "decision_agent"
    _log(state, "exit")
    return state