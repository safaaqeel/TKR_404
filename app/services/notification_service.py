"""
Central place to create/dispatch in-app notifications (and later
email/SMS via the tools/ integrations). Agents call this rather than
writing directly to a notifications table, so the schema can change once.
"""
from typing import Dict
import time


def create_notification(user_id: str, notif_type: str, title: str, body: str, tone: str = "amber") -> Dict:
    """tone: 'red' | 'amber' | 'green' — matches the frontend dot-color convention."""
    notification = {
        "id": f"notif_{int(time.time() * 1000)}",
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "body": body,
        "tone": tone,
        "created_at": time.time(),
        "read": False,
    }
    # TODO: persist to database/json store; publish to websocket if connected
    return notification
