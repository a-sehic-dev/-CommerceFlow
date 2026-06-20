"""Lightweight in-memory sliding-window rate limits (per IP / session key)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class SlidingWindowLimiter:
    def __init__(self, *, window_seconds: float, max_events: int) -> None:
        self.window_seconds = window_seconds
        self.max_events = max_events
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def check(self, key: str, *, cooldown_seconds: float = 0) -> None:
        now = time.time()
        bucket = self._events[key]
        self._trim(bucket, now)
        if cooldown_seconds > 0 and bucket and now - bucket[-1] < cooldown_seconds:
            wait = cooldown_seconds - (now - bucket[-1])
            raise HTTPException(
                429,
                detail=f"Please wait {wait:.0f}s before trying again.",
            )
        if len(bucket) >= self.max_events:
            raise HTTPException(
                429,
                detail="Upload limit reached. Try again in about an hour or sign in for a private workspace.",
            )
        bucket.append(now)

    def reset(self) -> None:
        self._events.clear()
