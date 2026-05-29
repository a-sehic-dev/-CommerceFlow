"""In-process guards against concurrent imports of the same file."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_active_ids: set[int] = set()
_active_filenames: set[str] = set()
_lock = asyncio.Lock()


def normalize_filename(name: str) -> str:
    return name.strip().lower()


async def has_active_imports() -> bool:
    async with _lock:
        return bool(_active_ids)


async def is_filename_busy(filename: str) -> bool:
    key = normalize_filename(filename)
    async with _lock:
        return key in _active_filenames


async def release_import(import_id: int, filename: str | None = None) -> None:
    """Clear in-memory locks after cancel, stale recovery, or crashed worker."""
    key = normalize_filename(filename) if filename else None
    async with _lock:
        _active_ids.discard(import_id)
        if key:
            _active_filenames.discard(key)


async def release_all_imports() -> None:
    """Clear orphaned in-memory locks after worker restart (DB may show no active import)."""
    async with _lock:
        _active_ids.clear()
        _active_filenames.clear()


@asynccontextmanager
async def claim_import(import_id: int, filename: str):
    key = normalize_filename(filename)
    async with _lock:
        if _active_filenames:
            raise RuntimeError("Another import is already in progress. Please wait until it finishes.")
        if key in _active_filenames:
            raise RuntimeError(f"Import already running for file: {filename}")
        _active_ids.add(import_id)
        _active_filenames.add(key)
    try:
        yield
    finally:
        await release_import(import_id, filename)
