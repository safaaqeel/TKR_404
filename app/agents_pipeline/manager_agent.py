"""
Purpose:    Orchestrator entry point for the agent workflow. Invoked by
            workflows/workflow_manager.py as the first (and re-entry) node
            in the agent graph on every turn.
Inputs:     AgentState (see workflows/workflow_manager.py §4) with at least
            "task_id" and "user_query" populated.
Outputs:    Mutated AgentState with "context" (memory context merged in on
            the first turn), "next_agent" set to route the graph, and
            "status" updated ("planning" | "running" | "awaiting_review" |
            "completed").
Depends on: agents/memory_agent.py (read_memory_context helper only),
            workflows/workflow_manager.py (AgentState schema).
Called by:  workflows/workflow_manager.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    # workflow_manager.py may not be importable in isolation (unit tests,
    # standalone tooling) — fall back to a plain dict alias.
    AgentState = Dict[str, Any]  # type: ignore

from agents_pipeline.memory_agent import read_memory_context

AGENT_NAME = "manager_agent"


def _log(state: AgentState, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": AGENT_NAME,
            "message": message,
        }
    )


def run(state: AgentState) -> AgentState:
    """Entry point invoked by the workflow graph for every Manager turn.

    Per §4, agents never call each other's run() functions directly — this
    function only mutates state["next_agent"]; workflow_manager.py performs
    the actual routing between graph nodes.
    """
    _log(state, "enter")

    # 1. First turn for this task: pull durable memory into context and
    #    hand off to the Planner.
    if state.get("plan") is None:
        state.setdefault("context", {})
        state["context"]["memory"] = read_memory_context(state.get("task_id", ""))
        state["status"] = "planning"
        state["next_agent"] = "planner_agent"
        _log(state, "no plan yet -> routing to planner_agent")
        _log(state, "exit")
        return state

    plan = state["plan"]
    idx = state.get("current_step_index", 0)

    # 2. Plan finished: hand off to Memory Agent to persist anything learned.
    if idx >= len(plan):
        state["status"] = "completed"
        state["next_agent"] = "memory_agent"
        _log(state, "plan complete -> routing to memory_agent")
        _log(state, "exit")
        return state

    step = plan[idx]

    # 3. High-risk step: require explicit confirmation before dispatch.
    #    POST /api/tasks/{id}/confirm is what flips state["status"] to
    #    "confirmed" between turns.
    if step.get("risk") == "high" and state.get("status") != "confirmed":
        state["status"] = "awaiting_review"
        state["next_agent"] = None
        _log(state, f"step {step.get('step')} is high-risk -> awaiting_review")
        _log(state, "exit")
        return state

    # 4. Route to whichever agent owns this step. Preserve "confirmed" here
    #    rather than unconditionally overwriting it to "running" — automation_agent
    #    runs its own independent high-risk gate (per its docstring, "enforced
    #    here independently of Manager Agent's own gate") and needs to still see
    #    status="confirmed" when it's dispatched, or that second gate would
    #    immediately re-trigger awaiting_review right after a human just
    #    approved the step. automation_agent flips status to "running" itself
    #    once its own check passes.
    state["status"] = "confirmed" if state.get("status") == "confirmed" else "running"
    state["next_agent"] = step.get("agent")
    _log(state, f"routing to {step.get('agent')} for step {step.get('step')}")
    _log(state, "exit")
    return state