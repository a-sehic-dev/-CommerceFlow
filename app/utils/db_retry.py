"""SQLite busy/locked retry helpers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger("commerceflow.db")

T = TypeVar("T")

_MAX_ATTEMPTS = 6
_BASE_DELAY = 0.05


def _is_locked(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


async def with_db_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    label: str = "db",
    max_attempts: int = _MAX_ATTEMPTS,
) -> T:
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except OperationalError as exc:
            last = exc
            if not _is_locked(exc) or attempt >= max_attempts - 1:
                raise
            delay = _BASE_DELAY * (2**attempt)
            logger.warning("%s locked (attempt %s/%s), retry in %.2fs", label, attempt + 1, max_attempts, delay)
            await asyncio.sleep(delay)
    assert last is not None
    raise last


async def flush_session(session, *, label: str = "flush") -> None:
    await with_db_retry(session.flush, label=label)


async def commit_session(session, *, label: str = "commit") -> None:
    await with_db_retry(session.commit, label=label)
