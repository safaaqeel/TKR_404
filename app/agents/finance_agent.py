"""
Finance Agent. Analyzes revenue, expenses, cash position, and debt to
produce the 'Recommendation Summary' shown on the Dashboard and feeds
the Decision Board / CEO Agent synthesis.
Powers: Dashboard 'Recommendation Summary', AI Decision Board 'Finance Agent' card.
"""
from __future__ import annotations

from typing import Any, Dict


def _ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


async def analyze(business_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    business_profile expects (all optional, sane defaults applied):
        revenue, expenses, cash_balance, receivables_days, payables_days,
        debt_to_equity, monthly_growth_rate
    Returns a structured recommendation, not free text — the UI renders
    problem/cause/action/improvement/time fields directly.
    """
    revenue = float(business_profile.get("revenue", 0))
    expenses = float(business_profile.get("expenses", 0))
    cash_balance = float(business_profile.get("cash_balance", 0))
    receivables_days = float(business_profile.get("receivables_days", 30))
    payables_days = float(business_profile.get("payables_days", 30))
    debt_to_equity = float(business_profile.get("debt_to_equity", 0.5))

    gross_margin = _ratio(revenue - expenses, revenue)
    cash_runway_months = _ratio(cash_balance, expenses / 12) if expenses else 12.0

    findings = []

    if gross_margin < 0.10:
        findings.append({
            "priority": "High",
            "problem": "Thin or negative gross margin",
            "cause": f"Expenses are consuming {round((1 - gross_margin) * 100)}% of revenue",
            "action": "Review pricing and identify the top 3 cost line items to renegotiate or cut",
            "improvement": f"+{round((0.15 - gross_margin) * revenue):,} INR/mo if margin reaches 15%" if gross_margin < 0.15 else "Margin already near target",
            "time": "3-4 weeks",
        })

    if receivables_days > payables_days + 15:
        findings.append({
            "priority": "High",
            "problem": "Receivables aging beyond payables terms",
            "cause": f"Customers pay in ~{int(receivables_days)} days but suppliers are paid in ~{int(payables_days)} days",
            "action": "Introduce an early-payment discount and automate payment reminders at day 7/14/21",
            "improvement": f"Up to {round((receivables_days - payables_days) / 30 * expenses):,} INR freed in working capital",
            "time": "2-3 weeks",
        })

    if cash_runway_months < 2:
        findings.append({
            "priority": "High",
            "problem": "Thin cash buffer",
            "cause": f"Current cash covers only {round(cash_runway_months, 1)} months of expenses",
            "action": "Set aside 5% of weekly revenue automatically into a reserve account",
            "improvement": "Extends runway by roughly 2-3 weeks per month of saving",
            "time": "Ongoing, review monthly",
        })
    elif cash_runway_months < 4:
        findings.append({
            "priority": "Medium",
            "problem": "Below-target cash buffer",
            "cause": f"Cash covers {round(cash_runway_months, 1)} months; target is 4-6 months for this business size",
            "action": "Build reserve gradually while monitoring receivables collection",
            "improvement": "Reduces distress risk exposure during seasonal dips",
            "time": "2-3 months",
        })

    if debt_to_equity > 2.0:
        findings.append({
            "priority": "Medium",
            "problem": "High leverage relative to equity",
            "cause": f"Debt-to-equity ratio is {round(debt_to_equity, 2)}, above the 2.0 comfort threshold",
            "action": "Pause new borrowing; prioritize paying down highest-interest debt first",
            "improvement": "Improves interest coverage and lender confidence for future credit",
            "time": "1-2 quarters",
        })

    if not findings:
        findings.append({
            "priority": "Low",
            "problem": "No urgent financial issues detected",
            "cause": "Margin, cash runway, and leverage are within healthy ranges",
            "action": "Maintain current discipline; revisit this analysis monthly",
            "improvement": "Sustained financial stability",
            "time": "Ongoing",
        })

    findings.sort(key=lambda f: {"High": 0, "Medium": 1, "Low": 2}[f["priority"]])

    return {
        "agent": "Finance Agent",
        "gross_margin": round(gross_margin * 100, 1),
        "cash_runway_months": round(cash_runway_months, 1),
        "debt_to_equity": round(debt_to_equity, 2),
        "recommendations": findings,
        "summary": findings[0]["action"],
        "confidence": 90 if len(findings) <= 2 else 78,
    }