"""
Purpose:    Quality gate. Checks the most recently completed step's output
            against its stated goal using a strict pass/fail rubric prompt,
            and routes back to Manager Agent for retry/replan on failure.
Inputs:     AgentState with "plan"/"current_step_index" and the
            corresponding entry already present in state["result"].
Outputs:    Mutated AgentState with a pass/fail verdict recorded at
            state["result"][step_key]["decision"], "next_agent" =
            "manager_agent" (or None + status="failed" if a step exhausts
            its retries).
Depends on: models/prompt_templates.py (DECISION_PROMPT), models/model_loader.py
            (Gemini client), workflows/workflow_manager.py (AgentState schema).
Called by:  workflows/workflow_manager.py (via manager_agent's next_agent routing)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from workflows.workflow_manager import AgentState  # type: ignore
except ImportError:
    AgentState = Dict[str, Any]  # type: ignore

from models.model_loader import get_llm_client
from models.prompt_templates import build_decision_prompt

AGENT_NAME = "decision_agent"
MAX_RETRIES_PER_STEP = 2


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


def _judge(client, goal: str, output: Any) -> Dict[str, Any]:
    prompt = build_decision_prompt(step_action=goal, step_result=output)
    raw = client.generate(prompt)
    try:
        raw_verdict = json.loads(_strip_code_fence(raw))
        # DECISION_PROMPT (models/prompt_templates.py) asks the LLM for
        # {"verdict": "pass"|"fail", "reason": ...} — normalize to an
        # internal {"pass": bool, "reason": str} shape so every downstream
        # check in this module (verdict.get("pass")) has one boolean
        # contract to rely on, regardless of the LLM's exact string case.
        verdict = {
            "pass": str(raw_verdict.get("verdict", "")).strip().lower() == "pass",
            "reason": raw_verdict.get("reason", ""),
        }
    except (json.JSONDecodeError, AttributeError):
        # Fail closed: an unparsable verdict is treated as a failed check,
        # never a silent pass.
        verdict = {"pass": False, "reason": "decision agent returned a non-JSON verdict"}
    return verdict


def run(state: AgentState) -> AgentState:
    _log(state, "enter")

    plan = state.get("plan") or []
    idx = max(state.get("current_step_index", 0) - 1, 0)  # the step that just ran
    step = plan[idx] if idx < len(plan) else {}
    step_key = f"step_{step.get('step', idx)}"
    step_result = state.get("result", {}).get(step_key, {})

    client = get_llm_client()
    verdict = _judge(client, step.get("action", ""), step_result)
    step_result["decision"] = verdict
    state.setdefault("result", {})[step_key] = step_result

    if verdict.get("pass"):
        _log(state, f"step {step.get('step', idx)} passed decision gate")
        state["next_agent"] = "manager_agent"
    else:
        retries = step.get("_retries", 0) + 1
        step["_retries"] = retries
        _log(state, f"step {step.get('step', idx)} failed decision gate: {verdict.get('reason')}")

        if retries > MAX_RETRIES_PER_STEP:
            state["status"] = "failed"
            state["error_detail"] = f"Step {step.get('step', idx)} failed quality gate after {retries} attempts."
            state["next_agent"] = None
            _log(state, "max retries exceeded -> status=failed")
        else:
            # Send the step back for a retry via Manager's routing.
            state["current_step_index"] = idx
            state["next_agent"] = "manager_agent"
            _log(state, f"retrying step {step.get('step', idx)} (attempt {retries})")

    _log(state, "exit")
    return state