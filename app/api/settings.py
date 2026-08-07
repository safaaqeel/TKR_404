"""
Settings persistence. Powers the Settings page — profile, alert
preferences, appearance.

NOTE: GET /api/settings and PUT /api/settings are owned by app/routes.py
(the legacy_router, mounted first in app/main.py) — that implementation
reads/writes database/user_data.json directly with no required params.
A GET "" was previously declared here too; it was dead code (routes.py's
route always won the path+method match since its router is included
first) and has been removed to avoid the confusing duplicate registration.
PATCH "" is kept as a distinct, not-yet-wired-up per-user update path —
it doesn't collide with routes.py's PUT (different HTTP method).
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    full_name: str | None = None
    business_name: str | None = None
    email: str | None = None
    alert_risk: bool | None = None
    alert_schemes: bool | None = None
    alert_supplier: bool | None = None
    weekly_summary_email: bool | None = None
    dark_mode: bool | None = None
    compact_sidebar: bool | None = None


@router.patch("")
async def update_settings(user_id: str, payload: SettingsUpdate):
    updates = payload.dict(exclude_unset=True)
    # TODO: persist `updates` to database/json store, keyed by user_id
    return {"updated": list(updates.keys())}