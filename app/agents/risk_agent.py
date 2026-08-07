"""
Risk Agent. Wraps app/ml/risk_prediction.py (XGBoost) with a transparent
rule-based fallback so the Dashboard 'Financial Distress Risk' card and
AI Decision Board work even before the model artifacts are trained.
Powers: Dashboard risk card, AI Decision Board 'Risk Agent' card.
"""
from __future__ import annotations

from typing import Any, Dict


async def analyze(business_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    business_profile expects: revenue, expenses, cash_balance,
    receivables_days, payables_days, inventory_turnover, debt_to_equity
    """
    from app.models import model_loader
    from app.ml.risk_prediction import predict_risk_score

    features = {
        "revenue": float(business_profile.get("revenue", 0)),
        "expenses": float(business_profile.get("expenses", 0)),
        "cash_balance": float(business_profile.get("cash_balance", 0)),
        "receivables_days": float(business_profile.get("receivables_days", 45)),
        "payables_days": float(business_profile.get("payables_days", 30)),
        "inventory_turnover": float(business_profile.get("inventory_turnover", 6)),
        "debt_to_equity": float(business_profile.get("debt_to_equity", 0.5)),
    }

    model = model_loader.get_risk_model()
    scaler = model_loader.get_risk_scaler()

    if model is not None and scaler is not None:
        try:
            result = predict_risk_score(features, model, scaler)
            return {
                "agent": "Risk Agent",
                "risk_score": result["risk_score"],
                "risk_band": result["risk_band"],
                "top_factors": result["top_factors"],
                "source": "xgboost_model",
                "confidence": 95,
            }
        except Exception:
            pass  # fall through to rule-based

    # Transparent rule-based fallback (not random) — used until the model
    # is trained, or if inference fails for any reason.
    margin = (features["revenue"] - features["expenses"]) / features["revenue"] if features["revenue"] else 0
    dso_penalty = max(0, features["receivables_days"] - features["payables_days"]) / 2
    leverage_penalty = features["debt_to_equity"] * 10
    score = max(0, min(100, round(50 - margin * 100 + dso_penalty + leverage_penalty)))
    band = "High" if score >= 65 else "Moderate" if score >= 35 else "Low"

    top_factors = sorted(
        [
            ("gross_margin", round(margin * 100, 1)),
            ("receivables_vs_payables_gap", round(dso_penalty, 1)),
            ("debt_to_equity", features["debt_to_equity"]),
        ],
        key=lambda kv: abs(kv[1]), reverse=True,
    )[:3]

    return {
        "agent": "Risk Agent",
        "risk_score": score,
        "risk_band": band,
        "top_factors": top_factors,
        "source": "rule_based_fallback",
        "confidence": 70,
    }