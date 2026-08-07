"""
Purpose:    Outbound webhook / HTTP POST tool used by
            agents/automation_agent.py for "webhook" actions.
Inputs:     post(url, payload, timeout=10) — target URL and a
            JSON-serializable payload.
Outputs:    dict with status_code and the parsed (or raw text) response
            body. Raises on unrecoverable failure after retries.
Depends on: MAX_RETRIES (.env, §12.1), the `requests` package (§12.2).
            Retried per §14's shared @with_retry(max_attempts=3,
            backoff="exponential") policy — implemented locally, mirroring
            tools/email_tool.py (see that file's docstring for why it isn't
            imported from a shared module).
Called by:  agents/automation_agent.py (dispatch table, "webhook");
            tools/notification_tool.py (routes "webhook" channel here)
"""

from __future__ import annotations

import functools
import os
import time
from typing import Any, Callable, Dict, Optional, TypeVar

import requests

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
                except Exception as exc:  # noqa: BLE001 - network errors vary
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    time.sleep((2 ** (attempt - 1)) if backoff == "exponential" else 1)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


@with_retry(max_attempts=int(os.environ.get("MAX_RETRIES", 3)), backoff="exponential")
def post(url: str, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    """POSTs a JSON payload to an outbound webhook URL. Raises on failure."""
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    return {"status_code": response.status_code, "body": body}