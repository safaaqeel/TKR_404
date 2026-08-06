"""
Purpose:    SMTP send tool used exclusively by agents/automation_agent.py
            for "send_email" actions.
Inputs:     send(to, subject, body) — plain-text email fields.
Outputs:    dict describing the outcome (recipient, subject, any refused
            addresses). Raises on unrecoverable send failure after retries.
Depends on: NOTIFICATION_SMTP_HOST, NOTIFICATION_SMTP_PORT,
            NOTIFICATION_EMAIL_FROM (see .env, §12.1). Retried per §14's
            shared @with_retry(max_attempts=3, backoff="exponential")
            policy — implemented locally here since tools/ sits below app/
            in the import hierarchy (§3.3) and cannot import app/config.py;
            env vars are therefore read directly, same as tools/web_tool.py.
Called by:  agents/automation_agent.py (dispatch table, "send_email");
            tools/notification_tool.py (routes "email" channel here)
"""

from __future__ import annotations

import functools
import os
import smtplib
import time
from email.mime.text import MIMEText
from typing import Any, Callable, Dict, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(max_attempts: int = 3, backoff: str = "exponential") -> Callable[[F], F]:
    """Shared retry policy per §14. Never applied to validation errors —
    callers should validate inputs before the wrapped call runs."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - SMTP errors vary
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    time.sleep((2 ** (attempt - 1)) if backoff == "exponential" else 1)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


@with_retry(max_attempts=int(os.environ.get("MAX_RETRIES", 3)), backoff="exponential")
def send(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Sends a plain-text email via SMTP. Raises on failure (see retry)."""
    host = os.environ.get("NOTIFICATION_SMTP_HOST")
    port = int(os.environ.get("NOTIFICATION_SMTP_PORT", 587))
    sender = os.environ.get("NOTIFICATION_EMAIL_FROM")

    if not host or not sender:
        raise RuntimeError(
            "NOTIFICATION_SMTP_HOST and NOTIFICATION_EMAIL_FROM must be set in .env"
        )

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to

    # Optional auth vars — not in the §12.1 .env list, but most real SMTP
    # relays require them. Harmless no-ops if unset.
    smtp_user = os.environ.get("NOTIFICATION_SMTP_USER")
    smtp_password = os.environ.get("NOTIFICATION_SMTP_PASSWORD")

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        refused = server.sendmail(sender, [to], message.as_string())

    return {"to": to, "subject": subject, "refused": refused}