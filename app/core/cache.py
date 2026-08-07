"""
In-process TTL cache. Swap the backing dict for Redis later without
changing call sites - every consumer only ever calls get/set/invalidate.

Why this exists: dashboard, reports, and RAG queries were being recomputed
on every request. This is the single highest-leverage fix for the
"dashboard loads slowly" complaint.
"""
import time
from typing import Any, Callable, Optional

_store: dict = {}


def get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _store.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    _store[key] = (time.time() + ttl_seconds, value)


def invalidate(key: str) -> None:
    _store.pop(key, None)


def invalidate_prefix(prefix: str) -> None:
    for k in [k for k in _store if k.startswith(prefix)]:
        _store.pop(k, None)


async def get_or_compute(key: str, compute: Callable, ttl_seconds: int = 300):
    """Cache-aside helper for async route handlers.

    Usage:
        data = await get_or_compute(f"dashboard:{user_id}", lambda: build_dashboard(user_id))
    """
    cached = get(key)
    if cached is not None:
        return cached
    import inspect
    value = await compute() if inspect.iscoroutinefunction(compute) else compute()
    set(key, value, ttl_seconds)
    return value
