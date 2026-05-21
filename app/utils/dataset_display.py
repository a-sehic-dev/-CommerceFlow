"""Friendly labels, company detection, and internal QA dataset filtering."""
from __future__ import annotations

import re
from pathlib import Path

# Legacy / seed filenames -> portfolio-friendly labels
FRIENDLY_NAMES: dict[str, str] = {
    "sales_valid.xlsx": "Demo Sales Dataset",
    "sales_valid.csv": "Demo Sales Dataset",
    "products_valid.xlsx": "Demo Products Catalog",
    "products_valid.csv": "Demo Products Catalog",
    "inventory_valid.xlsx": "Demo Inventory Dataset",
    "inventory_valid.csv": "Demo Inventory Dataset",
    "sales_sample.csv": "Demo Sales Dataset",
    "products_sample.csv": "Demo Products Catalog",
    "inventory_sample.csv": "Demo Inventory Dataset",
    "sales_nike_q1_2025.xlsx": "Nike — Q1 2025 Sales",
    "products_nike_catalog.xlsx": "Nike — Product Catalog",
    "inventory_nike_warehouse.xlsx": "Nike — Warehouse Inventory",
    "sales_apple_store_q1_2025.xlsx": "Apple Store — Q1 2025 Sales",
    "products_apple_catalog.xlsx": "Apple — Product Catalog",
    "inventory_apple_warehouse.xlsx": "Apple — Warehouse Inventory",
    "sales_zara_global_q1_2025.xlsx": "Zara Global — Q1 2025 Sales",
    "products_zara_catalog.xlsx": "Zara — Product Catalog",
    "inventory_zara_warehouse.xlsx": "Zara — Warehouse Inventory",
    "Demo Sales Dataset.xlsx": "Demo Sales Dataset",
    "Demo Products Catalog.xlsx": "Demo Products Catalog",
    "Demo Inventory Dataset.xlsx": "Demo Inventory Dataset",
}

COMPANY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"nike", re.I), "Nike"),
    (re.compile(r"apple", re.I), "Apple"),
    (re.compile(r"zara", re.I), "Zara"),
]

INTERNAL_MARKERS = (
  "_qa_",
  "_broken_",
  "_invalid_",
  "_corrupt_",
  "internal_",
  "test_only",
)

INTERNAL_FILENAMES = frozenset({
    "sales_missing_columns.xlsx",
    "sales_missing_columns.csv",
    "products_no_sku.xlsx",
    "products_no_sku.csv",
    "inventory_empty.xlsx",
    "inventory_empty.csv",
    "mixed_headers_confuse.xlsx",
    "sales_duplicate_headers.csv",
})


def basename(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name


def _strip_extensions(name: str) -> str:
    """Remove repeated extensions (e.g. report.xlsx.xlsx -> report)."""
    stem = Path(name).stem
    while stem and stem != name and Path(stem).suffix:
        name = stem
        stem = Path(name).stem
    return stem or name


def humanize_filename(filename: str) -> str:
    """Display label from basename only — never infer dataset type from the name."""
    core = _strip_extensions(basename(filename))
    label = re.sub(r"[_\-]+", " ", core).strip()
    return label.title() if label else basename(filename)


def is_internal_dataset(filename: str) -> bool:
    name = basename(filename).lower()
    if name in {f.lower() for f in INTERNAL_FILENAMES}:
        return True
    if name.startswith("internal_"):
        return True
    return any(m in name for m in INTERNAL_MARKERS)


def detect_company_name(filename: str) -> str | None:
    name = basename(filename)
    for pattern, label in COMPANY_PATTERNS:
        if pattern.search(name):
            return label
    return None


def resolve_display_name(filename: str) -> str:
    name = basename(filename)
    return FRIENDLY_NAMES.get(name, FRIENDLY_NAMES.get(name.lower(), humanize_filename(filename)))


def dataset_type_short(dtype: str) -> str:
    return {
        "sales": "SALES",
        "products": "PRODUCTS",
        "inventory": "INVENTORY",
        "mixed": "MIXED",
    }.get((dtype or "").lower(), "UNKNOWN")
