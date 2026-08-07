"""
Cashflow forecasting - separate from revenue_prediction.py because cashflow
needs payables/receivables timing, not just top-line revenue trend.
Powers: Dashboard 'Cash Flow Trend' chart, Financial Recovery Plan target dates.
"""
from typing import Dict, List


def forecast_cashflow(
    current_balance: float,
    projected_inflows: List[float],
    projected_outflows: List[float],
) -> Dict:
    """Simple rolling projection; swap for Prophet/ARIMA once historical
    weekly cashflow data is available in sufficient volume."""
    balance = current_balance
    trajectory = []
    for inflow, outflow in zip(projected_inflows, projected_outflows):
        balance += inflow - outflow
        trajectory.append(round(balance, 2))

    runway_breach_week = next((i for i, b in enumerate(trajectory) if b < 0), None)

    return {
        "trajectory": trajectory,
        "runway_breach_week": runway_breach_week,
        "ending_balance": trajectory[-1] if trajectory else current_balance,
    }
