"""Display-only margin percent formatting (raw analytics values unchanged)."""

from __future__ import annotations

import math
from typing import Any


def margin_out_of_display_range(value: Any) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if math.isnan(v) or math.isinf(v):
        return False
    return v < -100.0 or v > 100.0


def format_margin_display(value: Any, *, decimals: int = 1) -> str:
    """Format margin % for UI and Excel text cells without altering stored values."""
    if value is None or value == "":
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(v):
        return "—"
    if v < -100.0:
        return "<-100%"
    if v > 100.0:
        return ">100%"
    return f"{v:.{decimals}f}%"


def margin_percent_excel_value(value: Any) -> tuple[Any, str]:
    """
    Return (cell_value, number_format) for openpyxl.
    Out-of-range margins are written as text; in-range use fractional percent.
    """
    general_fmt = "General"
    pct_fmt = "0.0%"

    if margin_out_of_display_range(value):
        return format_margin_display(value), general_fmt
    try:
        v = float(value)
        if abs(v) > 1.5:
            v = v / 100.0
        return v, pct_fmt
    except (TypeError, ValueError):
        return format_margin_display(value), general_fmt
