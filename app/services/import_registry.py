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
        async with _lock:
            _active_ids.discard(import_id)
            _active_filenames.discard(key)
