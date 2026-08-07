"""
Growth Agent. Combines competitor position, matched government schemes,
and revenue/risk trend to produce actionable growth opportunities.
Powers: Growth Opportunities page, AI Decision Board 'Growth Agent' card.
"""
from __future__ import annotations

from typing import Any, Dict, List


async def analyze(
    business_profile: Dict[str, Any],
    finance_output: Dict[str, Any],
    risk_output: Dict[str, Any],
    competitor_output: Dict[str, Any],
    scheme_output: Dict[str, Any],
) -> Dict[str, Any]:
    opportunities: List[Dict[str, Any]] = []

    # Signal 1: competitor position — if below median, that's a growth gap;
    # if above median, that's a strength to double down on.
    if competitor_output.get("available"):
        for w in competitor_output.get("weaknesses", []):
            if "No significant" in w:
                continue
            opportunities.append({
                "priority": "Medium",
                "problem": w,
                "cause": "Below-median performance versus similar businesses in your segment",
                "action": "Benchmark your pricing and operating costs against segment leaders and close the gap incrementally",
                "improvement": "Move toward segment median performance",
                "time": "2-3 months",
            })
        for s in competitor_output.get("strengths", []):
            if "No standout" in s:
                continue
            opportunities.append({
                "priority": "Low",
                "problem": f"Underleveraged strength: {s}",
                "cause": "Above-median performance not yet reflected in market positioning",
                "action": "Use this strength in marketing/positioning to win share from weaker competitors",
                "improvement": "Faster customer acquisition at similar spend",
                "time": "1 month",
            })

    # Signal 2: unclaimed government schemes are direct growth capital.
    top_schemes = scheme_output.get("eligible_schemes", [])[:3]
    for sch in top_schemes:
        opportunities.append({
            "priority": "High" if sch["probability_of_approval"] >= 60 else "Medium",
            "problem": f"Unclaimed scheme: {sch['scheme_name']}",
            "cause": sch["reason"],
            "action": f"Apply via {sch['application_mode']} — {sch['benefit_type']}",
            "improvement": f"Up to ₹{sch['benefit_amount_inr']:,}" if sch.get("benefit_amount_inr") else "Non-monetary benefit",
            "time": "3-6 weeks",
        })

    # Signal 3: only recommend expansion moves if risk is not already High —
    # growth advice that ignores distress risk is actively harmful.
    risk_band = risk_output.get("risk_band", "Moderate")
    if risk_band != "High":
        margin = finance_output.get("gross_margin", 0)
        if margin >= 15:
            opportunities.append({
                "priority": "Medium",
                "problem": "Healthy margin not yet reinvested",
                "cause": f"Gross margin of {margin}% is above the 15% reinvestment threshold",
                "action": "Pilot one growth lever (new SKU, new channel, or new territory) with a capped budget",
                "improvement": "Diversified revenue base",
                "time": "1-2 quarters",
            })
    else:
        opportunities.insert(0, {
            "priority": "High",
            "problem": "Growth moves are premature given current risk level",
            "cause": f"Financial distress risk is currently {risk_band}",
            "action": "Stabilize via the Financial Recovery Plan before committing budget to growth initiatives",
            "improvement": "Avoids compounding financial strain",
            "time": "Immediate",
        })

    opportunities.sort(key=lambda o: {"High": 0, "Medium": 1, "Low": 2}[o["priority"]])

    return {
        "agent": "Growth Agent",
        "opportunities": opportunities[:8],
        "gated_by_risk": risk_band == "High",
    }