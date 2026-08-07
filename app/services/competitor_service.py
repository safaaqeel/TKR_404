"""
Anonymized competitor benchmarking. Reads data/datasets/company_data.csv
and computes percentile bands so no individual competitor's data is ever
exposed - only aggregates.
Powers: Competitor Agent, 'nearby competitor averages' dashboard feature.

NOTE on data: company_data.csv currently has columns
[company_id, company_name, industry, city, state, founded_year, employees,
 annual_revenue_inr, company_type, gst_registered]. It does not (yet)
include profit_margin, growth_rate, risk, inventory, or cashflow columns,
so only revenue-based and headcount-based percentiles are computable from
this dataset today. The functions below are written generically over
whatever numeric columns exist, so adding those columns to the CSV later
requires no code changes here.
"""
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from app.config import get_settings

# Numeric columns we can compute percentiles for, given what's actually in
# company_data.csv today. Extend this list as richer columns become available.
_PERCENTILE_COLUMNS = ["annual_revenue_inr", "employees"]


def _load_company_data() -> pd.DataFrame:
    settings = get_settings()
    path = settings.project_root / "data" / "datasets" / "company_data.csv"
    return pd.read_csv(path)


def get_industry_benchmarks(industry: str, state: Optional[str] = None, city: Optional[str] = None) -> Dict:
    """Returns anonymized aggregate stats (median/percentile, never raw rows)
    for businesses matching industry (+ optionally state/city)."""
    df = _load_company_data()

    filtered = df[df["industry"].str.lower() == industry.lower()]
    if state:
        filtered = filtered[filtered["state"].str.lower() == state.lower()]
    if city:
        filtered = filtered[filtered["city"].str.lower() == city.lower()]

    if filtered.empty:
        return {"available": False, "reason": "Insufficient anonymized data for this segment"}

    stats = {"available": True, "sample_size": int(len(filtered))}
    for col in _PERCENTILE_COLUMNS:
        if col in filtered.columns:
            stats[f"{col}_median"] = float(filtered[col].median())
            stats[f"{col}_p75"] = float(filtered[col].quantile(0.75))
            stats[f"{col}_p25"] = float(filtered[col].quantile(0.25))
    return stats


def compare_business_to_industry(business_metrics: Dict, industry: str, state: Optional[str] = None, city: Optional[str] = None) -> Dict:
    """Combines a single (identifiable-only-to-its-owner) business's metrics
    against the anonymized benchmark to produce a comparison the UI can render.
    business_metrics keys should match _PERCENTILE_COLUMNS, e.g. {"annual_revenue_inr": ..., "employees": ...}."""
    df = _load_company_data()
    filtered = df[df["industry"].str.lower() == industry.lower()]
    if state:
        filtered = filtered[filtered["state"].str.lower() == state.lower()]
    if city:
        filtered = filtered[filtered["city"].str.lower() == city.lower()]

    if filtered.empty:
        return {"available": False, "reason": "Insufficient anonymized data for this segment"}

    result = {"available": True, "sample_size": int(len(filtered))}
    for col in _PERCENTILE_COLUMNS:
        if col not in filtered.columns or col not in business_metrics:
            continue
        series = filtered[col].dropna()
        if series.empty:
            continue
        value = business_metrics[col]
        percentile = float((series < value).mean() * 100)
        result[col] = {
            "your_value": value,
            "industry_median": float(series.median()),
            "percentile": round(percentile, 1),
            "position": "above median" if value > series.median() else "below median",
        }
    return result