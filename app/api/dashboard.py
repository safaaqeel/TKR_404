"""
Dashboard endpoints. Powers: Financial Distress Risk, Business Pulse Score,
Revenue Trend, Cash Flow Trend, and all the metric cards.
"""
from fastapi import APIRouter
from app.core.cache import get_or_compute

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(business_id: str):
    async def _build():
        # TODO: call analytics_service.compute_business_health_score,
        # ml.risk_prediction.predict_risk_score, ml.revenue_prediction.forecast_revenue
        return {"health_score": 78, "risk": {"score": 31, "band": "Moderate"}}

    return await get_or_compute(f"dashboard:{business_id}", _build, ttl_seconds=300)
