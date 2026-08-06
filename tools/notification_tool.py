"""
Purpose:    Generic notification dispatcher used by
            agents/automation_agent.py for "notify" actions. Wraps
            email_tool and web_tool rather than implementing any delivery
            logic itself.
Inputs:     notify(channel, message) — channel is "email" or "webhook";
            message is a dict of channel-specific fields (see below).
Outputs:    dict describing the outcome from the underlying tool call.
Depends on: tools/email_tool.py, tools/web_tool.py.
Called by:  agents/automation_agent.py (dispatch table, "notify")
"""

from __future__ import annotations

from typing import Any, Dict

from tools import email_tool, web_tool


def notify(channel: str, message: Dict[str, Any]) -> Dict[str, Any]:
    """Routes a notification to the right underlying tool by channel.

    Expected `message` shape per channel:
      - "email":   {"to": str, "subject": str, "body": str}
      - "webhook": {"url": str, "payload": dict}
    """
    if channel == "email":
        return email_tool.send(to=message["to"], subject=message["subject"], body=message["body"])
    if channel == "webhook":
        return web_tool.post(url=message["url"], payload=message["payload"])

    raise ValueError(f"Unknown notification channel: {channel!r}")