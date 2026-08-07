"""
Anonymous competitor benchmarking endpoints.
"""
from fastapi import APIRouter
from app.agents.competitor_agent import analyze

router = APIRouter(prefix="/api/competitor", tags=["competitor"])


@router.get("/benchmark")
async def get_competitor_benchmark(business_id: str, sector: str, district: str | None = None):
    # TODO: load real business_metrics from database by business_id
    business_metrics = {"revenue": 4200000, "profit_margin": 0.14}
    return await analyze(business_metrics, sector, district)
