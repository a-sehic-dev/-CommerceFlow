"""Selection fingerprints and cache keys (no service imports — avoids circular deps)."""

from __future__ import annotations


def analysis_cache_key(selection: dict[str, int | None]) -> str:
    p = selection.get("products_import_id") or 0
    s = selection.get("sales_import_id") or 0
    i = selection.get("inventory_import_id") or 0
    return f"analysis_{p}_{s}_{i}"


def selection_fingerprint(selection: dict[str, int | None]) -> str:
    p = selection.get("products_import_id") or 0
    s = selection.get("sales_import_id") or 0
    i = selection.get("inventory_import_id") or 0
    return f"CF-{p}-{s}-{i}"


def unified_cache_key(selection: dict[str, int | None]) -> str:
    return f"unified_{analysis_cache_key(selection)}"


def unified_snapshot_type(selection: dict[str, int | None]) -> str:
    return f"unified_{analysis_cache_key(selection)}"
