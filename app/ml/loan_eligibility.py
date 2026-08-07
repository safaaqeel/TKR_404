"""
Loan / government-scheme eligibility scoring.
Powers: Government Schemes page, Scheme Agent, Financial Recovery Plan funding options.

Rule-based first (transparent, explainable to judges); can be upgraded to a
learned model once labeled approval/rejection outcome data exists.
"""
from typing import Dict, List


def score_loan_eligibility(business_profile: Dict) -> Dict:
    """
    business_profile expects keys like: annual_turnover, years_operating,
    existing_debt, credit_score, msme_category, sector.
    Returns an eligibility score (0-100) and which scheme tiers likely qualify.
    """
    score = 50
    reasons: List[str] = []

    if business_profile.get("years_operating", 0) >= 2:
        score += 15
        reasons.append("Established business (2+ years)")
    if business_profile.get("credit_score", 0) >= 700:
        score += 20
        reasons.append("Strong credit history")
    if business_profile.get("existing_debt", 0) / max(business_profile.get("annual_turnover", 1), 1) < 0.4:
        score += 15
        reasons.append("Healthy debt-to-turnover ratio")

    score = min(score, 100)
    tier = "High eligibility" if score >= 75 else "Moderate eligibility" if score >= 50 else "Low eligibility"

    return {"eligibility_score": score, "tier": tier, "reasons": reasons}
