import time
from typing import Any


class SimpleTTLCache:
    """In-memory TTL cache placeholder for future Redis integration."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def invalidate(self, prefix: str | None = None) -> None:
        if prefix is None:
            self._store.clear()
            return
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]


analytics_cache = SimpleTTLCache()
