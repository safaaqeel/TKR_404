"""
Recovery Agent. Turns Finance Agent + Risk Agent findings into a concrete
30/60/90 day action plan.
Powers: Financial Recovery Plan page.
"""
from __future__ import annotations

from typing import Any, Dict, List


async def analyze(finance_output: Dict[str, Any], risk_output: Dict[str, Any]) -> Dict[str, Any]:
    risk_band = risk_output.get("risk_band", "Moderate")
    findings = finance_output.get("recommendations", [])
    high_priority = [f for f in findings if f.get("priority") == "High"]
    medium_priority = [f for f in findings if f.get("priority") == "Medium"]

    plan_30: List[Dict[str, str]] = []
    plan_60: List[Dict[str, str]] = []
    plan_90: List[Dict[str, str]] = []

    # Day 30: stop the bleeding — address every High priority finding first.
    for f in high_priority:
        plan_30.append({"title": f["problem"], "body": f["action"]})
    if not high_priority:
        plan_30.append({"title": "Stabilize baseline", "body": "No high-priority issues found; maintain current financial discipline and re-check weekly."})
    if risk_band == "High":
        plan_30.append({"title": "Daily risk monitoring", "body": "Escalate distress-risk tracking to daily review until the score drops below 65."})

    # Day 60: consolidate — medium priority items + start of structural fixes.
    for f in medium_priority:
        plan_60.append({"title": f["problem"], "body": f["action"]})
    plan_60.append({"title": "Reassess cash runway", "body": "Recompute cash runway using the last 30 days of actuals; adjust reserve target if needed."})

    # Day 90: build resilience — forward-looking, not just firefighting.
    plan_90.append({"title": "Build a 90-day cash reserve", "body": "Target 3 months of operating expenses in reserve, funded by the 5% weekly set-aside."})
    plan_90.append({"title": "Re-forecast", "body": "Review recovery progress against this plan's targets and set the next 90-day cycle."})
    if risk_band != "Low":
        plan_90.append({"title": "Diversify revenue concentration", "body": "Reduce dependency on top clients/products identified as risk factors."})

    return {
        "agent": "Recovery Agent",
        "risk_band_at_creation": risk_band,
        "day_30": plan_30,
        "day_60": plan_60,
        "day_90": plan_90,
    }