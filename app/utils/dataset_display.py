"""Friendly labels, company detection, and internal QA dataset filtering."""
from __future__ import annotations

import re
from pathlib import Path

OPERATIONAL_DATASET_NAMES: dict[str, str] = {
    "sales": "Retail Sales Dataset",
    "products": "Product Operations Dataset",
    "inventory": "Inventory Operations Dataset",
}

MODULE_ENGINE_TITLES: dict[str, str] = {
    "sales": "Sales Intelligence Engine",
    "products": "Product Intelligence Engine",
    "inventory": "Inventory Operations Engine",
}

MODULE_STATUS_LABELS: dict[str, str] = {
    "sales": "Sales Intelligence Active",
    "products": "Product Intelligence Active",
    "inventory": "Inventory Operations Active",
}

DEMO_FILE_TYPES: dict[str, str] = {
    "sales_valid.xlsx": "sales",
    "sales_valid.csv": "sales",
    "products_valid.xlsx": "products",
    "products_valid.csv": "products",
    "inventory_valid.xlsx": "inventory",
    "inventory_valid.csv": "inventory",
    "sales_sample.csv": "sales",
    "products_sample.csv": "products",
    "inventory_sample.csv": "inventory",
    "atlas_inventory.xlsx": "inventory",
    "atlas_products.xlsx": "products",
    "atlas_sales_q1_2026.xlsx": "sales",
    "Demo Sales Dataset.xlsx": "sales",
    "Demo Products Catalog.xlsx": "products",
    "Demo Inventory Dataset.xlsx": "inventory",
}

FRIENDLY_NAMES: dict[str, str] = {
    name: OPERATIONAL_DATASET_NAMES[dtype]
    for name, dtype in DEMO_FILE_TYPES.items()
}

DEMO_FILENAMES = frozenset(name.lower() for name in DEMO_FILE_TYPES)

COMPANY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"atlas", re.I), "Atlas Retail Group"),
    (re.compile(r"northwind", re.I), "Northwind Retail"),
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
    stem = Path(name).stem
    while stem and stem != name and Path(stem).suffix:
        name = stem
        stem = Path(name).stem
    return stem or name


def _infer_dtype_from_filename(filename: str) -> str | None:
    lower = basename(filename).lower()
    if lower in DEMO_FILE_TYPES:
        return DEMO_FILE_TYPES[lower]
    if re.search(r"(^|_)sales(_|\.|$)", lower):
        return "sales"
    if re.search(r"(^|_)products(_|\.|$)", lower):
        return "products"
    if re.search(r"(^|_)inventory(_|\.|$)", lower):
        return "inventory"
    return None


def humanize_filename(filename: str) -> str:
    core = _strip_extensions(basename(filename))
    label = re.sub(r"[_\-]+", " ", core).strip()
    label = re.sub(r"\bq([1-4])\b", r"Q\1", label, flags=re.I)
    label = re.sub(r"\b(20\d{2})\s+(sales|inventory|products?)\b", r"\2 \1", label, flags=re.I)
    words = []
    for word in label.split():
        if re.fullmatch(r"q[1-4]", word, flags=re.I):
            words.append(word.upper())
        elif re.fullmatch(r"20\d{2}", word):
            words.append(word)
        else:
            words.append(word.capitalize())
    label = " ".join(words)
    label = re.sub(r"\bSales\s+Q([1-4])\s+(20\d{2})\b", r"Q\1 \2 Sales Dataset", label)
    label = re.sub(r"\bInventory\s+Export\b", "Inventory Export", label)
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


def detect_workspace_key(filename: str) -> str | None:
    lower = basename(filename).lower()
    for slug in ("atlas",):
        if lower.startswith(f"{slug}_") or slug in lower:
            return slug
    return None


def is_demo_dataset(filename: str) -> bool:
    return basename(filename).lower() in DEMO_FILENAMES


def dataset_source_label(filename: str) -> str:
    return "Sample Data" if is_demo_dataset(filename) else "Uploaded"


def module_engine_title(dtype: str) -> str:
    return MODULE_ENGINE_TITLES.get((dtype or "").lower(), "Analytics Engine")


def module_status_label(dtype: str) -> str:
    return MODULE_STATUS_LABELS.get((dtype or "").lower(), "Dataset Connected")


def operational_dataset_name(dtype: str) -> str:
    return OPERATIONAL_DATASET_NAMES.get((dtype or "").lower(), "Operational Dataset")


def resolve_display_name(filename: str, dataset_type: str | None = None) -> str:
    """Import history / picker title — includes company grouping for demo packs."""
    name = basename(filename)
    lower = name.lower()
    if lower in DEMO_FILENAMES or name in FRIENDLY_NAMES:
        dtype = dataset_type or _infer_dtype_from_filename(name)
        operational = operational_dataset_name(dtype) if dtype else FRIENDLY_NAMES.get(name, name)
        company = detect_company_name(name)
        if company:
            return f"{company} — {operational}"
        return operational
    humanized = humanize_filename(filename)
    if dataset_type and dataset_type.lower() in OPERATIONAL_DATASET_NAMES:
        lowered = humanized.lower()
        if any(token in lowered for token in ("sales", "product", "inventory", "catalog", "warehouse")):
            return humanized
        return operational_dataset_name(dataset_type)
    return humanized


def format_dataset_metadata(
    *,
    rows: int,
    started_at,
    filename: str,
    dataset_type: str,
) -> str:
    ts = started_at.strftime("%b %d, %I:%M %p") if started_at else ""
    parts: list[str] = []
    if rows:
        parts.append(f"{rows:,} rows")
    if ts:
        parts.append(f"Imported {ts}")
    company = detect_company_name(filename)
    if company and is_demo_dataset(filename):
        parts.append(company)
    return " · ".join(parts)


def dataset_type_short(dtype: str) -> str:
    return {
        "sales": "SALES",
        "products": "PRODUCTS",
        "inventory": "INVENTORY",
        "mixed": "MIXED",
    }.get((dtype or "").lower(), "UNKNOWN")
