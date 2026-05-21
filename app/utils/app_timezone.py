"""Application timezone — Europe/Sarajevo (Bosnia & Herzegovina)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Europe/Sarajevo")
APP_TZ_NAME = "Europe/Sarajevo"


def now_local() -> datetime:
    """Timezone-aware current time in Europe/Sarajevo."""
    return datetime.now(APP_TZ)


def naive_local_now() -> datetime:
    """Wall-clock local time for SQLite DateTime columns (no tz suffix in DB)."""
    return datetime.now(APP_TZ).replace(tzinfo=None)


def ensure_local(dt: datetime) -> datetime:
    """Attach or convert to Europe/Sarajevo."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=APP_TZ)
    return dt.astimezone(APP_TZ)


def as_local_iso(dt: datetime | None) -> str | None:
    """ISO-8601 string with offset for API / JSON."""
    if dt is None:
        return None
    return ensure_local(dt).isoformat()


def format_display(dt: datetime | None) -> str:
    """Human-readable local timestamp for exports and logs."""
    if dt is None:
        return "—"
    local = ensure_local(dt)
    return local.strftime("%Y-%m-%d %H:%M:%S")


def filename_timestamp() -> str:
    return now_local().strftime("%Y%m%d_%H%M%S")
