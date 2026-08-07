"""
CEO Agent. Synthesizes Finance, Risk, Growth, Recovery, Competitor, and
Scheme Agent outputs into one prioritized final recommendation.
Powers: AI Decision Board 'CEO Agent' card / final recommendation banner.
"""
from __future__ import annotations

from typing import Any, Dict


async def synthesize(specialist_outputs: Dict[str, Any]) -> Dict[str, Any]:
    finance = specialist_outputs.get("finance", {})
    risk = specialist_outputs.get("risk", {})
    growth = specialist_outputs.get("growth", {})
    recovery = specialist_outputs.get("recovery", {})

    risk_band = risk.get("risk_band", "Moderate")
    top_finance_issue = (finance.get("recommendations") or [{}])[0]

    if risk_band == "High":
        headline = "Stabilize before expanding"
        rationale = (
            f"Distress risk is High ({risk.get('risk_score', '?')}/100). "
            f"The top financial issue — {top_finance_issue.get('problem', 'cash pressure')} — "
            "should be addressed via the 30-day Recovery Plan before any growth spend."
        )
        primary_action = top_finance_issue.get("action", "Follow the 30-day recovery plan")
    elif risk_band == "Moderate":
        headline = "Fix the binding constraint, then grow selectively"
        rationale = (
            f"Distress risk is Moderate ({risk.get('risk_score', '?')}/100). "
            f"Resolve '{top_finance_issue.get('problem', 'the top finance issue')}' first, "
            "then pursue the highest-confidence growth opportunity."
        )
        primary_action = top_finance_issue.get("action", "Address the top finance recommendation")
    else:
        headline = "Financially stable — proceed with growth plan"
        rationale = f"Distress risk is Low ({risk.get('risk_score', '?')}/100) and margins are healthy."
        top_opportunity = (growth.get("opportunities") or [{}])[0]
        primary_action = top_opportunity.get("action", "Continue current growth initiatives")

    try:
        from app.services.gemini_service import generate
        narrative_prompt = (
            "You are a CEO advisor for an Indian MSME. In 2-3 sentences, "
            f"summarize this situation for the business owner: risk band={risk_band}, "
            f"top finance issue={top_finance_issue.get('problem')}, "
            f"recommended action={primary_action}. Be direct and practical."
        )
        narrative = await generate(narrative_prompt, temperature=0.3)
    except Exception:
        narrative = rationale  # deterministic fallback if Gemini is unavailable

    return {
        "agent": "CEO Agent",
        "headline": headline,
        "rationale": rationale,
        "narrative": narrative,
        "primary_action": primary_action,
        "risk_band": risk_band,
        "confidence": min(
            finance.get("confidence", 80),
            risk.get("confidence", 80),
        ),
        "recovery_plan_available": bool(recovery.get("day_30")),
    }