"""
Purpose:    Structured-data reasoning over data/datasets/*.csv using pandas,
            for plan steps that need numeric/tabular analysis rather than
            semantic document retrieval.
Inputs:     AgentState with "plan"/"current_step_index" pointing at a step
            whose "agent" == "analysis_agent". Expected step shape (set by
            the Planner): {"dataset": str, "operation": str, "column": str,
            "filters": dict | None}.
Outputs:    Mutated AgentState with state["result"][step_key] containing
            the computed value(s) and the exact pandas operation performed
            (for auditability), or a structured error on failure.
            "next_agent" = "manager_agent".
Depends on: data/datasets/*.csv, workflows/workflow_manager.py (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent routing)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

AGENT_NAME = "analysis_agent"
DATASETS_DIR = Path("data/datasets")


def _log(state: AgentState, message: str) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": AGENT_NAME,
            "message": message,
        }
    )


def _load_dataset(name: str) -> pd.DataFrame:
    path = DATASETS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_csv(path)


def _run_operation(step: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the pandas operation described by the step.

    Always returns a dict recording the exact operation performed, since
    every numeric claim must be auditable back to a specific pandas call.
    """
    dataset_name = step.get("dataset", "sample_data.csv")
    operation = step.get("operation", "describe")
    column = step.get("column")
    filters = step.get("filters") or {}

    df = _load_dataset(dataset_name)

    for col, val in filters.items():
        df = df[df[col] == val]

    if operation == "groupby" and column:
        value = df.groupby(column).size().to_dict()
        op_desc = f"df.groupby('{column}').size()"
    elif operation == "value_counts" and column:
        value = df[column].value_counts().to_dict()
        op_desc = f"df['{column}'].value_counts()"
    elif operation == "filter":
        value = df.to_dict(orient="records")
        op_desc = f"df[filters={filters}]"
    else:
        value = df.describe(include="all").to_dict()
        op_desc = "df.describe(include='all')"

    return {"dataset": dataset_name, "operation": op_desc, "value": value}


def run(state: AgentState) -> AgentState:
    _log(state, "enter")

    idx = state.get("current_step_index", 0)
    plan = state.get("plan") or []
    step = plan[idx] if idx < len(plan) else {}
    step_key = f"step_{step.get('step', idx)}"

    try:
        result = _run_operation(step)
        state.setdefault("result", {})[step_key] = result
        _log(state, f"computed {result['operation']} on {result['dataset']}")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        # Structured error, never a raw traceback surfaced to the user.
        state.setdefault("result", {})[step_key] = {
            "error": True,
            "message": f"Analysis failed: {exc}",
        }
        _log(state, f"analysis error: {exc}")

    state["current_step_index"] = idx + 1
    # Route through the quality gate before handing back to Manager, per
    # §5 of the governing spec (Decision reviews every completed step).
    state["next_agent"] = "decision_agent"
    _log(state, "exit")
    return state