"""
What-If Simulator endpoint. Powers the Simulator page: takes hypothetical
changes to hiring, machinery spend, loan amount, and pricing, and returns
projected revenue, profit, cashflow trajectory, risk score, and probability
of recovery. Reuses app/ml (forecasting, risk_prediction) and
app/services/analytics_service.py rather than reimplementing the math here.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ml.forecasting import forecast_cashflow
from app.services.analytics_service import compute_business_health_score

logger = logging.getLogger("smart_automation_ai.simulator")

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

PROJECTION_MONTHS = 6


class SimulatorRequest(BaseModel):
    # Baseline business figures. In production these should be looked up
    # from the business's stored profile/dataset by business_id; they're
    # accepted directly here too so the simulator works standalone.
    business_id: Optional[str] = None
    monthly_revenue: float = Field(180000, description="Current average monthly revenue (INR)")
    monthly_expenses: float = Field(140000, description="Current average monthly expenses (INR)")
    cash_balance: float = Field(250000, description="Current cash on hand (INR)")

    # What-if levers
    hire: int = Field(0, ge=0, description="Additional employees to hire")
    machinery: float = Field(0, ge=0, description="One-time machinery/equipment spend (INR)")
    loan: float = Field(0, ge=0, description="New loan amount taken (INR)")
    price_increase: float = Field(0, description="Price increase, percent")
    new_product: bool = False
    new_branch: bool = False


# --- Cost assumptions used to translate levers into monthly cash impact ----
# These are declared constants (not magic numbers scattered through the
# function) so they're easy to tune once real historical data is available
# to fit them against.
AVG_MONTHLY_SALARY = 22000          # INR per hire, fully loaded
MACHINERY_MONTHLY_MAINTENANCE_RATE = 0.01  # 1% of machinery cost / month upkeep
LOAN_MONTHLY_EMI_RATE = 0.02        # simplistic flat EMI rate per month
NEW_PRODUCT_MONTHLY_REVENUE_LIFT = 22000
NEW_PRODUCT_MONTHLY_COST = 9000
NEW_BRANCH_MONTHLY_REVENUE_LIFT = 60000
NEW_BRANCH_MONTHLY_COST = 95000     # branches cost more than they earn early on


@router.post("/run")
async def run_simulation(payload: SimulatorRequest):
    try:
        adjusted_revenue = payload.monthly_revenue * (1 + payload.price_increase / 100)
        if payload.new_product:
            adjusted_revenue += NEW_PRODUCT_MONTHLY_REVENUE_LIFT
        if payload.new_branch:
            adjusted_revenue += NEW_BRANCH_MONTHLY_REVENUE_LIFT

        adjusted_expenses = payload.monthly_expenses
        adjusted_expenses += payload.hire * AVG_MONTHLY_SALARY
        adjusted_expenses += payload.machinery * MACHINERY_MONTHLY_MAINTENANCE_RATE
        adjusted_expenses += payload.loan * LOAN_MONTHLY_EMI_RATE
        if payload.new_product:
            adjusted_expenses += NEW_PRODUCT_MONTHLY_COST
        if payload.new_branch:
            adjusted_expenses += NEW_BRANCH_MONTHLY_COST

        monthly_profit = adjusted_revenue - adjusted_expenses

        # Cashflow trajectory: machinery + product/branch setup costs hit
        # cash in month 1 as one-off outflows; everything else is recurring.
        inflows = [adjusted_revenue] * PROJECTION_MONTHS
        outflows = [adjusted_expenses] * PROJECTION_MONTHS
        outflows[0] += payload.machinery  # one-off capex hits the first month

        # Loan proceeds land as cash in month 1 (offsetting the capex it likely funds)
        starting_balance = payload.cash_balance + payload.loan

        cashflow = forecast_cashflow(
            current_balance=starting_balance,
            projected_inflows=inflows,
            projected_outflows=outflows,
        )

        # Risk score: use the trained model if available, otherwise a
        # transparent rule-based fallback so the endpoint still returns a
        # real, non-random figure instead of failing.
        risk_score, risk_band, risk_source = _estimate_risk(
            monthly_revenue=adjusted_revenue,
            monthly_expenses=adjusted_expenses,
            cash_balance=starting_balance,
        )

        health_score = compute_business_health_score({
            "revenue_momentum": 70 if monthly_profit > 0 else 35,
            "cash_conversion_cycle": 60,
            "debt_service_coverage": 75 if payload.loan == 0 else 45,
            "customer_concentration": 60,
            "working_capital_ratio": 65 if cashflow["ending_balance"] > 0 else 30,
            "expense_volatility": 60,
        })

        probability_of_recovery = _probability_of_recovery(
            monthly_profit=monthly_profit,
            runway_breach_week=cashflow["runway_breach_week"],
            risk_score=risk_score,
        )

        return {
            "inputs": payload.model_dump(),
            "projected_monthly_revenue": round(adjusted_revenue, 2),
            "projected_monthly_expenses": round(adjusted_expenses, 2),
            "projected_monthly_profit": round(monthly_profit, 2),
            "cashflow": cashflow,
            "risk": {"score": risk_score, "band": risk_band, "source": risk_source},
            "business_health_score": health_score,
            "probability_of_recovery": probability_of_recovery,
            "graph": {
                "months": [f"Month {i + 1}" for i in range(PROJECTION_MONTHS)],
                "cash_trajectory": cashflow["trajectory"],
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Simulator run failed")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")


def _estimate_risk(monthly_revenue: float, monthly_expenses: float, cash_balance: float):
    """Use the trained XGBoost risk model when available; otherwise fall
    back to a transparent ratio-based rule so the endpoint never returns
    fake/random numbers."""
    from app.models import model_loader
    from app.ml.risk_prediction import predict_risk_score

    model = model_loader.get_risk_model()
    scaler = model_loader.get_risk_scaler()

    if model is not None and scaler is not None:
        try:
            result = predict_risk_score(
                business_features={
                    "revenue": monthly_revenue,
                    "expenses": monthly_expenses,
                    "cash_balance": cash_balance,
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
            logger.warning("Risk model inference failed, falling back to rule-based: %s", exc)

    # Rule-based fallback (transparent, not random): margin-based heuristic.
    margin = (monthly_revenue - monthly_expenses) / monthly_revenue if monthly_revenue else 0
    score = max(0, min(100, round(50 - margin * 100)))
    band = "High" if score >= 65 else "Moderate" if score >= 35 else "Low"
    return score, band, "rule_based_fallback"


def _probability_of_recovery(monthly_profit: float, runway_breach_week, risk_score: float) -> float:
    """Simple, explainable blend: positive cashflow + low risk score = high
    probability; cash running out soon = low probability, regardless of
    what the risk model says."""
    if runway_breach_week is not None:
        return round(max(5.0, 40.0 - risk_score / 3), 1)
    base = 90.0 - risk_score * 0.6
    if monthly_profit > 0:
        base += 8
    return round(max(5.0, min(95.0, base)), 1)