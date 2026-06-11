# tests/test_database_url.py

from datetime import datetime, timezone

from app.utils.app_timezone import to_db_datetime
from app.utils.database_url import (
    is_postgres_url,
    is_sqlite_url,
    mask_database_url,
    normalize_async_database_url,
)


def test_normalize_render_postgres_url():
    raw = "postgres://user:secret@dpg-abc-a.frankfurt-postgres.render.com/commerceflow"
    assert normalize_async_database_url(raw) == (
        "postgresql+asyncpg://user:secret@dpg-abc-a.frankfurt-postgres.render.com/commerceflow"
    )


def test_normalize_postgresql_url():
    raw = "postgresql://user:secret@localhost/db"
    assert normalize_async_database_url(raw) == "postgresql+asyncpg://user:secret@localhost/db"


def test_sqlite_url_unchanged():
    raw = "sqlite+aiosqlite:///./data/commerceflow.db"
    assert normalize_async_database_url(raw) == raw
    assert is_sqlite_url(raw)
    assert not is_postgres_url(raw)


def test_mask_database_url_hides_password():
    raw = "postgresql+asyncpg://user:secret@host/db"
    masked = mask_database_url(raw)
    assert "secret" not in masked
    assert "user" in masked


def test_to_db_datetime_strips_timezone():
    aware = datetime(2025, 1, 27, 15, 18, tzinfo=timezone.utc)
    naive = to_db_datetime(aware)
    assert naive is not None
    assert naive.tzinfo is None
