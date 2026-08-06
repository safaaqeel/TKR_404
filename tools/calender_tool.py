"""
Purpose:    Local/ICS calendar entry creation tool used by
            agents/automation_agent.py for "create_event" actions.
Inputs:     create_event(title, when, notes=None) — `when` is an ISO-8601
            datetime string; `notes` is optional free text.
Outputs:    dict with the generated event's uid and the relative path of
            the .ics file written.
Depends on: tools/file_tool.py — all writes go through it (§15), this
            module never calls open() directly.
Called by:  agents/automation_agent.py (dispatch table, "create_event")
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from tools import file_tool


def _to_ics_datetime(when: str) -> str:
    dt = datetime.fromisoformat(when)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_event(title: str, when: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """Creates a single-event .ics file under data/uploads/ and returns its path.

    data/uploads/ is the only writable, non-curated bucket in the canonical
    folder tree (§2) — generated .ics files live there rather than in a new
    subfolder, since the spec's tree is fixed and "any file reference must
    use these paths and only these paths."
    """
    event_uid = f"{uuid.uuid4()}@smart-automation-ai"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dtstart = _to_ics_datetime(when)

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Smart Automation AI//EN",
        "BEGIN:VEVENT",
        f"UID:{event_uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart}",
        f"SUMMARY:{title}",
    ]
    if notes:
        ics_lines.append(f"DESCRIPTION:{notes}")
    ics_lines += ["END:VEVENT", "END:VCALENDAR"]

    file_path = f"data/uploads/event_{event_uid.split('@')[0]}.ics"
    file_tool.write(file_path, "\n".join(ics_lines))

    return {"uid": event_uid, "path": file_path, "title": title, "when": when}