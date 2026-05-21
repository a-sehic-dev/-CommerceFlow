"""Upload file extension helpers (filename-agnostic parsing)."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_SUFFIXES = frozenset({".csv", ".xlsx", ".xls"})


def resolve_upload_suffix(filename: str) -> str:
    """
    Return the effective data suffix for a upload name.

    Handles double extensions such as ``report.xlsx.xlsx`` by walking stems until
    a supported suffix is found or none remain.
    """
    name = Path(filename.replace("\\", "/")).name
    path = Path(name)
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return suffix
    stem = path.stem
    if stem and stem != name:
        return resolve_upload_suffix(stem)
    return suffix


def is_supported_upload(filename: str) -> bool:
    return resolve_upload_suffix(filename) in SUPPORTED_SUFFIXES
