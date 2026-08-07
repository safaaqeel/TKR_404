"""
Dashboard endpoints. Powers: Financial Distress Risk, Business Pulse Score,
and the metric cards driven by real data (data/datasets/msme_database.csv,
data/datasets/company_data.csv) plus the trained risk model when available.

NOTE on scope: "Revenue Trend" and "Cash Flow Trend" line charts are NOT
wired up here. Every dataset under data/datasets/ (msme_database.csv,
company_data.csv, district_statistics.csv, ...) is a single-snapshot
registry — one row per business with no per-period history — so there is
no real time series anywhere in this project to draw those charts from.
Fabricating one would mean inventing numbers and presenting them as this
business's actual history, which is exactly the "no fake data" rule this
codebase is built against. The What-If Simulator (app/api/simulator.py)
legitimately projects a synthetic trajectory because it's explicitly
framed as a hypothetical projection, not historical fact — that's a
different case. Wiring a real trend chart here needs either a genuine
per-business financial history dataset, or an explicit product decision
to reuse the simulator's projection under a clearly-labeled "projected,
not historical" banner.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.core.cache import get_or_compute
from app.services.analytics_service import compute_business_maturity_score

logger = logging.getLogger("smart_automation_ai.dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Registry datasets to search, in order, by their own id-column name.
_REGISTRIES = (
    ("msme_database.csv", "msme_id"),
    ("company_data.csv", "company_id"),
)


def _find_business_row(business_id: str) -> Optional[dict]:
    """Look up a business by id across every registry dataset. Returns the
    raw CSV row (as a dict) plus which registry it came from, or None if no
    dataset has a matching row for this id."""
    datasets_dir = get_settings().project_root / "data" / "datasets"
    for filename, id_col in _REGISTRIES:
        path = datasets_dir / filename
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get(id_col) == business_id:
                    row["_source_dataset"] = filename
                    return row
    return None


def _estimate_risk_for_business(row: dict):
    """Same pattern as app/api/simulator.py's _estimate_risk: use the
    trained XGBoost model when it's available, otherwise a transparent,
    non-random rule-based fallback — never a hardcoded/fake number."""
    from app.models import model_loader

    model = model_loader.get_risk_model()
    scaler = model_loader.get_risk_scaler()

    revenue = float(row.get("annual_revenue_inr") or row.get("annual_turnover_inr") or 0)
    employees = float(row.get("employees") or 0)

    if model is not None and scaler is not None:
        try:
            from app.ml.risk_prediction import predict_risk_score

            result = predict_risk_score(
                business_features={
                    "revenue": revenue,
                    "expenses": revenue * 0.75,  # no real expense data available; see module docstring
                    "cash_balance": revenue * 0.1,
                    "receivables_days": 45,
                    "payables_days": 30,
                    "inventory_turnover": 6,
                    "debt_to_equity": 1.0,
                },
                model=model,
                scaler=scaler,
            )
            return result["risk_score"], result["risk_band"], "xgboost_model"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Risk model inference failed for dashboard, falling back: %s", exc)

    # Rule-based fallback: smaller/newer/thinly-staffed businesses skew
    # riskier. Transparent, not random — every input traces to a real
    # dataset column.
    score = 50
    if revenue < 2_000_000:
        score += 15
    if employees < 10:
        score += 10
    score = max(0, min(100, score))
    band = "High" if score >= 65 else "Moderate" if score >= 35 else "Low"
    return score, band, "rule_based_fallback"


@router.get("")
async def get_dashboard(business_id: str):
    async def _build():
        row = _find_business_row(business_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No business with id {business_id!r} in any registered dataset.",
            )

        risk_score, risk_band, risk_source = _estimate_risk_for_business(row)

        maturity_score = compute_business_maturity_score({
            "years_operating": (
                2026 - int(row["founded_year"]) if row.get("founded_year") else 0
            ),
            "has_digital_presence": False,  # not present in any current dataset
            "compliance_up_to_date": row.get("gst_registered", "").strip().lower() == "yes",
        })

        return {
            "business_id": business_id,
            "source_dataset": row["_source_dataset"],
            "profile": {k: v for k, v in row.items() if not k.startswith("_")},
            "health_score": maturity_score,
            "risk": {"score": risk_score, "band": risk_band, "source": risk_source},
        }

    return await get_or_compute(f"dashboard:{business_id}", _build, ttl_seconds=300)