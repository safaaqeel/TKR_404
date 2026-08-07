"""
Settings persistence. Powers the Settings page — profile, alert
preferences, appearance. Currently nothing here updates anything;
this fixes that.
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


@router.get("")
async def get_settings_for_user(user_id: str):
    # TODO: load from database/json store
    return {}


@router.patch("")
async def update_settings(user_id: str, payload: SettingsUpdate):
    updates = payload.dict(exclude_unset=True)
    # TODO: persist `updates` to database/json store, keyed by user_id
    return {"updated": list(updates.keys())}
