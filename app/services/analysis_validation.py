"""Strict dataset validation before analytics — blocks invalid analysis runs."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Each group: at least one column alias must be present in the dataframe.
DATASET_FIELD_GROUPS: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "sales": [
        ("sku", ("sku",)),
        ("quantity", ("quantity", "qty")),
        ("revenue", ("revenue", "price", "unit_price")),
        ("sold_at", ("sold_at", "order_date", "sale_date", "created_at", "date", "timestamp")),
    ],
    "products": [
        ("sku", ("sku",)),
        ("title", ("title", "name", "product_name")),
    ],
    "inventory": [
        ("sku", ("sku",)),
        ("stock", ("quantity_on_hand", "on_hand", "stock", "available_units", "quantity")),
    ],
}

DATASET_LABELS = {
    "sales": "Sales",
    "products": "Products",
    "inventory": "Inventory",
}


@dataclass
class ValidationResult:
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    empty_datasets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "warnings": self.warnings,
            "errors": self.errors,
            "missing_columns": self.missing_columns,
            "empty_datasets": self.empty_datasets,
        }


def _has_any_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> bool:
    cols = {str(c).strip().lower() for c in df.columns}
    return any(alias.lower() in cols for alias in aliases)


def _validate_dataset_frame(
    df: pd.DataFrame,
    dtype: str,
    *,
    required: bool,
    result: ValidationResult,
) -> None:
    label = DATASET_LABELS.get(dtype, dtype.title())
    key = dtype.lower()

    if df.empty:
        if required:
            result.empty_datasets.append(key)
            result.valid = False
            result.errors.append(f"{label} dataset is empty — import data before running analysis.")
        return

    missing: list[str] = []
    for field_name, aliases in DATASET_FIELD_GROUPS.get(dtype, []):
        if not _has_any_column(df, aliases):
            missing.append(field_name)

    if missing:
        result.missing_columns[key] = missing
        result.valid = False
        result.errors.append(
            f"Missing required columns in {label} dataset: {', '.join(missing)}"
        )


def validate_datasets(
    products_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    selection: dict[str, int | None] | None = None,
) -> ValidationResult:
    """
    Validate required fields for each selected dataset type.
    Stops analysis when a selected dataset is empty or missing required columns.
    """
    result = ValidationResult()
    sel = selection or {}

    sales_required = bool(sel.get("sales_import_id"))
    products_required = bool(sel.get("products_import_id"))
    inventory_required = bool(sel.get("inventory_import_id"))

    if not sales_required and not products_required and not inventory_required:
        result.valid = False
        result.errors.append("Select at least one dataset (sales, products, or inventory) before running analysis.")
        return result

    _validate_dataset_frame(sales_df, "sales", required=sales_required, result=result)
    _validate_dataset_frame(products_df, "products", required=products_required, result=result)
    _validate_dataset_frame(inventory_df, "inventory", required=inventory_required, result=result)

    if (
        products_df.empty
        and sales_df.empty
        and inventory_df.empty
        and not result.errors
    ):
        result.valid = False
        result.errors.append(
            "No data available for analysis. Import CSV/XLSX files first."
        )

    return result
