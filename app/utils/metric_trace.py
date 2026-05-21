from typing import Any


def metric_trace(
    formula: str,
    dataset: str,
    row_count: int,
    value: Any = None,
    *,
    columns_used: list[str] | None = None,
    missing_columns: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "formula": formula,
        "dataset": dataset,
        "row_count": row_count,
        "value": value,
        "columns_used": columns_used or [],
        "missing_columns": missing_columns or [],
        "notes": notes,
    }
