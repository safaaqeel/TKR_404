"""
Competitor Agent. Anonymous benchmarking against data/datasets/company_data.csv
via app/services/competitor_service.py. Never exposes individual competitor
rows — only aggregate percentiles.
Powers: Competitor Intelligence page, AI Decision Board 'Competitor Agent' card.

Called as analyze(business_metrics, sector, district) by app/api/competitor.py
(sector/district are the caller's naming; mapped internally to the
industry/state fields that actually exist in company_data.csv).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


async def analyze(business_metrics: Dict[str, Any], sector: str, district: Optional[str] = None) -> Dict[str, Any]:
    from app.services.competitor_service import compare_business_to_industry

    # business_metrics may arrive with generic keys (revenue, profit_margin);
    # map to the columns competitor_service.py actually computes percentiles for.
    mapped_metrics = {}
    if "annual_revenue_inr" in business_metrics:
        mapped_metrics["annual_revenue_inr"] = business_metrics["annual_revenue_inr"]
    elif "revenue" in business_metrics:
        mapped_metrics["annual_revenue_inr"] = business_metrics["revenue"]
    if "employees" in business_metrics:
        mapped_metrics["employees"] = business_metrics["employees"]

    comparison = compare_business_to_industry(mapped_metrics, industry=sector, state=district)

    if not comparison.get("available"):
        return {
            "agent": "Competitor Agent",
            "available": False,
            "reason": comparison.get("reason", "Not enough anonymized data for this segment yet."),
        }

    strengths, weaknesses = [], []
    for field in ("annual_revenue_inr", "employees"):
        info = comparison.get(field)
        if not info:
            continue
        label = "Revenue" if field == "annual_revenue_inr" else "Headcount"
        if info["percentile"] >= 60:
            strengths.append(f"{label} is in the top {round(100 - info['percentile'])}% for this segment")
        elif info["percentile"] <= 40:
            weaknesses.append(f"{label} is below {info['percentile']}th percentile for this segment")

    return {
        "agent": "Competitor Agent",
        "available": True,
        "sample_size": comparison["sample_size"],
        "comparison": comparison,
        "strengths": strengths or ["No standout strengths detected from available metrics"],
        "weaknesses": weaknesses or ["No significant weaknesses detected from available metrics"],
    }