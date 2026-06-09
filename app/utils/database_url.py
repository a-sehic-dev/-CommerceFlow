"""Normalize DATABASE_URL for SQLAlchemy async (Render Postgres, local SQLite)."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_async_database_url(url: str) -> str:
    """Render uses postgres:// — async SQLAlchemy needs postgresql+asyncpg://."""
    raw = (url or "").strip()
    if not raw:
        return raw
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw.removeprefix("postgres://")
    if raw.startswith("postgresql://") and "+asyncpg" not in raw:
        return "postgresql+asyncpg://" + raw.removeprefix("postgresql://")
    return raw


def is_sqlite_url(url: str) -> bool:
    return (url or "").startswith("sqlite")


def is_postgres_url(url: str) -> bool:
    return (url or "").startswith("postgresql")


def mask_database_url(url: str) -> str:
    """Hide credentials in admin/debug responses."""
    if not url or is_sqlite_url(url):
        return url
    try:
        normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        parsed = urlparse(normalized)
        if not parsed.password:
            return url.split("@")[-1] if "@" in url else url
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        if parsed.username:
            netloc = f"{parsed.username}:***@{netloc}"
        return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
    except Exception:
        return "postgresql://***"
