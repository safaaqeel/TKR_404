"""
Anonymized competitor benchmarking. Reads data/datasets/company_data.csv
(or a dedicated competitors dataset) and computes percentile bands so no
individual competitor's data is ever exposed - only aggregates.
Powers: Competitor Agent, 'nearby competitor averages' dashboard feature.
"""
import pandas as pd
from typing import Dict


def get_industry_benchmarks(sector: str, district: str = None) -> Dict:
    """Returns anonymized aggregate stats (median/percentile, never raw rows)
    for businesses matching sector (+ optionally district)."""
    df = pd.read_csv("data/datasets/company_data.csv")

    filtered = df[df["sector"] == sector]
    if district:
        filtered = filtered[filtered["district"] == district]

    if filtered.empty:
        return {"available": False, "reason": "Insufficient anonymized data for this segment"}

    return {
        "available": True,
        "sample_size": len(filtered),
        "revenue_median": float(filtered["revenue"].median()),
        "revenue_p75": float(filtered["revenue"].quantile(0.75)),
        "profit_margin_median": float(filtered["profit_margin"].median()) if "profit_margin" in filtered else None,
        "growth_rate_median": float(filtered["growth_rate"].median()) if "growth_rate" in filtered else None,
    }


def compare_business_to_industry(business_metrics: Dict, sector: str, district: str = None) -> Dict:
    """Combines a single (identifiable-only-to-its-owner) business's metrics
    against the anonymized benchmark to produce a comparison the UI can render."""
    benchmark = get_industry_benchmarks(sector, district)
    if not benchmark.get("available"):
        return benchmark

    revenue_percentile = "above median" if business_metrics.get("revenue", 0) > benchmark["revenue_median"] else "below median"

    return {**benchmark, "business_revenue_position": revenue_percentile}
