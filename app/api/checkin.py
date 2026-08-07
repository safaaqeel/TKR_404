"""
Daily Check-in submission. Feeds the Memory Agent / Analysis Agent with
fresh operational signals between full analyses.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/checkin", tags=["checkin"])


class CheckinPayload(BaseModel):
    sales: float
    complaints: int
    delays: str
    inventory: str
    attendance: float
    expenses: float
    competitors: str
    marketchange: str | None = None
    feedback: str | None = None
    notes: str | None = None
    status: str = "submitted"


@router.post("")
async def submit_checkin(business_id: str, payload: CheckinPayload):
    # TODO: persist to database, trigger Memory Agent update,
    # invalidate dashboard cache for this business_id
    from app.core.cache import invalidate_prefix
    invalidate_prefix(f"dashboard:{business_id}")
    return {"ok": True, "status": payload.status}
