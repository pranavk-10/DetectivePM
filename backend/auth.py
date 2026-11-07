"""Admin authentication with a shared key, plus a limiter on failed attempts."""

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from backend.config import settings

MAX_FAILURES = 10
WINDOW_SECONDS = 60

_failures: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset_failures() -> None:
    with _lock:
        _failures.clear()


def _recent(client: str, now: float) -> deque[float]:
    attempts = _failures[client]
    while attempts and now - attempts[0] > WINDOW_SECONDS:
        attempts.popleft()
    return attempts


def require_admin(request: Request, x_admin_key: str | None = Header(default=None)) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin access is not configured on this server")
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        if len(_recent(client, now)) >= MAX_FAILURES:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts; try again shortly")
    if not x_admin_key or not hmac.compare_digest(x_admin_key.encode(), settings.admin_api_key.encode()):
        with _lock:
            _failures[client].append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "A valid admin key is required")
