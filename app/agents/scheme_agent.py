"""
Scheme Agent. Matches a business profile against
data/datasets/government_schemes.csv and returns eligible schemes with a
reason, benefit, application mode, and an approval-probability estimate.
Powers: Government Schemes page, AI Decision Board 'Scheme Agent' card.

NOTE on data: government_schemes.csv columns are
[scheme_id, scheme_name, ministry, category, launch_year, eligibility,
 benefit_type, benefit_amount_inr, application_mode, status].
'eligibility' is free text (e.g. "Women entrepreneurs", "SC/ST entrepreneurs"),
not separate structured columns for district/business_type/employees/etc.
Matching below is done by keyword-matching business_profile flags against
that eligibility text — the most that's honestly derivable from this data
without fabricating structure the CSV doesn't have.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from app.config import get_settings

_KEYWORD_FLAGS = {
    "women_owned": ["women"],
    "sc_st_owned": ["sc/st", "sc", "st"],
    "is_startup": ["startup"],
    "is_msme": ["msme", "micro", "small", "medium"],
    "minority_owned": ["minority"],
    "rural": ["rural"],
}


def _load_schemes() -> pd.DataFrame:
    settings = get_settings()
    path = settings.project_root / "data" / "datasets" / "government_schemes.csv"
    df = pd.read_csv(path)
    return df[df["status"].str.lower() == "active"]


def _eligibility_score(eligibility_text: str, business_profile: Dict[str, Any]) -> float:
    """Returns 0.0-1.0: how well the business's declared flags match this
    scheme's free-text eligibility. General-audience schemes (no matched
    keyword found at all) score a neutral 0.5 rather than 0, since absence
    of a keyword restriction usually means broadly eligible."""
    text = eligibility_text.lower()
    any_keyword_present = any(
        kw in text for kws in _KEYWORD_FLAGS.values() for kw in kws
    )
    if not any_keyword_present:
        return 0.5

    matched, total_relevant = 0, 0
    for flag, keywords in _KEYWORD_FLAGS.items():
        if any(kw in text for kw in keywords):
            total_relevant += 1
            if business_profile.get(flag):
                matched += 1
    return matched / total_relevant if total_relevant else 0.5


def _approval_probability(business_profile: Dict[str, Any], eligibility_score: float) -> int:
    credit_score = business_profile.get("credit_score", 650)
    years_operating = business_profile.get("years_operating", 1)
    existing_debt = business_profile.get("existing_debt", 0)
    annual_turnover = business_profile.get("annual_turnover", 1)

    debt_ratio = existing_debt / annual_turnover if annual_turnover else 1
    score = 40
    score += eligibility_score * 30
    score += min(years_operating * 3, 15)
    score += max(0, (credit_score - 600) / 10)
    score -= min(debt_ratio * 40, 25)
    return int(max(5, min(95, round(score))))


async def recommend_schemes(business_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    business_profile expects: sector, years_operating, credit_score,
    existing_debt, annual_turnover, and optionally the boolean flags in
    _KEYWORD_FLAGS (women_owned, is_startup, is_msme, etc.)
    """
    df = _load_schemes()
    results: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        elig_score = _eligibility_score(str(row["eligibility"]), business_profile)
        if elig_score < 0.34:
            continue  # not a plausible match — skip rather than pad results

        probability = _approval_probability(business_profile, elig_score)

        results.append({
            "scheme_id": row["scheme_id"],
            "scheme_name": row["scheme_name"],
            "ministry": row["ministry"],
            "category": row["category"],
            "reason": f"Matches eligibility criteria: {row['eligibility']}",
            "benefit_type": row["benefit_type"],
            "benefit_amount_inr": int(row["benefit_amount_inr"]) if pd.notna(row["benefit_amount_inr"]) else None,
            "application_mode": row["application_mode"],
            "application_link": f"https://www.udyamimitra.in/schemes/{row['scheme_id']}",
            "probability_of_approval": probability,
        })

    results.sort(key=lambda r: r["probability_of_approval"], reverse=True)

    return {
        "agent": "Scheme Agent",
        "eligible_schemes": results[:10],
        "total_matches": len(results),
    }