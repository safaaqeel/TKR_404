"""
Government Schemes matching. Powers the Government Schemes page —
connected to data/datasets/government_schemes.csv via the Scheme Agent.
"""
from fastapi import APIRouter

from app.agents.scheme_agent import recommend_schemes
from app.agents.orchestrator import _default_business_profile

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.get("/recommendations")
async def get_scheme_recommendations(business_id: str):
    # NOTE: business profile lookup by business_id is not yet backed by a
    # real store (no business-profile table exists in database/*.json yet).
    # Using the shared default profile keeps this consistent with the
    # AI Decision Board rather than inventing separate fake data here.
    business_profile = _default_business_profile(business_id)
    return await recommend_schemes(business_profile)