"""
Government Schemes matching. Powers the Government Schemes page —
currently unconnected to the schemes.csv / knowledge base at all.
"""
from fastapi import APIRouter
from app.agents.scheme_agent import recommend_schemes

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.get("/recommendations")
async def get_scheme_recommendations(business_id: str):
    # TODO: load real business_profile from database by business_id
    business_profile = {"sector": "manufacturing", "years_operating": 3, "credit_score": 720, "existing_debt": 200000, "annual_turnover": 4000000}
    return await recommend_schemes(business_profile)
