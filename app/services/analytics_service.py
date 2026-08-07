"""
Composite score calculations: Business Health Score, Business Maturity
Score, Financial Health Score. These aggregate ML outputs + rule-based
weighting into the single numbers shown on the dashboard gauge.
"""
from typing import Dict


def compute_business_health_score(signals: Dict) -> int:
    """
    signals expects sub-scores already computed elsewhere, e.g.:
    {revenue_momentum, cash_conversion_cycle, debt_service_coverage,
     customer_concentration, working_capital_ratio, expense_volatility}
    Weighted average -> single 0-100 score for the dashboard gauge.
    """
    weights = {
        "revenue_momentum": 0.20,
        "cash_conversion_cycle": 0.15,
        "debt_service_coverage": 0.20,
        "customer_concentration": 0.15,
        "working_capital_ratio": 0.15,
        "expense_volatility": 0.15,
    }
    score = sum(signals.get(k, 50) * w for k, w in weights.items())
    return round(score)


def compute_business_maturity_score(business_profile: Dict) -> int:
    """Considers years operating, process documentation, digital adoption,
    compliance history - a distinct axis from financial health."""
    score = 40
    score += min(business_profile.get("years_operating", 0) * 5, 25)
    score += 15 if business_profile.get("has_digital_presence") else 0
    score += 20 if business_profile.get("compliance_up_to_date") else -10
    return max(0, min(100, score))
