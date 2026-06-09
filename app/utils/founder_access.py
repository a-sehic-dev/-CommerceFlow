"""Protect founder-only admin APIs (usage insights, feedback inbox)."""

from fastapi import HTTPException, Query

from app.config import get_settings


def verify_founder_key(key: str | None) -> None:
    settings = get_settings()
    expected = (settings.usage_stats_key or "").strip()
    if not expected:
        if settings.app_env == "development" or settings.debug:
            return
        raise HTTPException(
            403,
            detail="Admin insights disabled. Set USAGE_STATS_KEY in the server environment.",
        )
    if not key or key != expected:
        raise HTTPException(403, detail="Invalid or missing admin key.")


def verify_founder_key_in_production(key: str | None = Query(default=None)) -> None:
    """Destructive admin actions: open in dev, require USAGE_STATS_KEY in production."""
    settings = get_settings()
    if settings.app_env == "development" or settings.debug:
        return
    verify_founder_key(key)
