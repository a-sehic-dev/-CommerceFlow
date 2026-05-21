"""Schema validation for analytics datasets — non-fatal warnings."""

from dataclasses import dataclass, field

import pandas as pd

PRODUCT_COLUMNS = {"sku", "title", "price"}
SALES_COLUMNS = {"sku", "revenue"}
INVENTORY_COLUMNS = {"sku", "quantity_on_hand"}


@dataclass
class ValidationResult:
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    empty_datasets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "warnings": self.warnings,
            "missing_columns": self.missing_columns,
            "empty_datasets": self.empty_datasets,
        }


def _missing(df: pd.DataFrame, required: set[str], name: str, result: ValidationResult) -> None:
    if df.empty:
        result.empty_datasets.append(name)
        result.warnings.append(f"{name} dataset is empty — related analytics may be limited")
        return
    missing = sorted(required - set(df.columns))
    if missing:
        result.missing_columns[name] = missing
        result.warnings.append(f"{name} missing columns: {', '.join(missing)}")
        result.valid = False


def validate_datasets(
    products_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
) -> ValidationResult:
    result = ValidationResult()
    _missing(products_df, PRODUCT_COLUMNS, "products", result)
    _missing(sales_df, SALES_COLUMNS, "sales", result)
    _missing(inventory_df, INVENTORY_COLUMNS, "inventory", result)

    if products_df.empty and sales_df.empty and inventory_df.empty:
        result.valid = False
        result.warnings.append(
            "No data in database. Upload products, sales, or inventory CSV files first."
        )
    return result
