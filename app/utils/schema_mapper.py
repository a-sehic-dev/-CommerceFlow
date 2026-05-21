"""Dynamic column detection and normalization for arbitrary ecommerce files."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Canonical field -> alias headers (normalized matching)
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "variant_sku", "product_sku", "item_sku", "code", "item_code"),
    "title": ("title", "name", "product_name", "product", "item_name", "description"),
    "price": ("price", "unit_price", "retail_price", "variant_price", "regular_price"),
    "compare_at_price": ("compare_at_price", "compare price", "msrp", "list_price"),
    "cost": ("cost", "unit_cost", "cogs", "landed_cost"),
    "category": ("category", "product_category", "type", "collection", "product_type"),
    "vendor": ("vendor", "brand", "manufacturer", "supplier"),
    "quantity": ("quantity", "qty", "units", "units_sold", "item_quantity", "lineitem quantity"),
    "revenue": (
        "revenue",
        "total",
        "line_total",
        "sales_amount",
        "gross_sales",
        "net_sales",
        "order_total",
        "amount",
        "transaction_amount",
    ),
    "sold_at": (
        "sold_at",
        "order_date",
        "sale_date",
        "created_at",
        "date",
        "timestamp",
        "transaction_date",
        "purchase_date",
    ),
    "order_id": ("order_id", "order_number", "order_no", "order", "name", "transaction_id", "invoice_id"),
    "customer": ("customer", "customer_name", "customer_id", "buyer", "email", "billing email"),
    "sales_channel": ("sales_channel", "channel", "source", "platform", "marketplace"),
    "discount_amount": ("discount_amount", "discount", "discounts", "line_discount"),
    "margin": ("margin", "margin_pct", "profit_margin", "gross_margin"),
    "status": ("status", "product_status", "active", "published"),
    "on_hand": (
        "on_hand",
        "quantity_on_hand",
        "qty_on_hand",
        "stock_on_hand",
        "inventory_qty",
        "stock_level",
        "qty_available",
    ),
    "available_units": ("available_units", "available", "available_stock", "sellable"),
    "reserved": ("reserved", "quantity_reserved", "reserved_qty", "allocated"),
    "inbound": ("inbound", "incoming", "on_order", "expected"),
    "stock": ("stock", "inventory", "units_on_hand"),
    "days_in_stock": ("days_in_stock", "days_in_inventory", "aging_days", "age_days"),
    "warehouse": ("warehouse", "location", "fulfillment_center", "store", "bin"),
}

REQUIRED_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "products": ("sku", "title"),
    "sales": ("revenue",),
    "inventory": ("sku",),
}


def normalize_header(name: Any) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    return s.strip("_")


def detect_schema(headers: list[str]) -> dict[str, Any]:
    """Map raw headers to canonical fields; ignore unknown columns."""
    norm_to_raw: dict[str, str] = {}
    for h in headers:
        norm_to_raw[normalize_header(h)] = h

    mapped: dict[str, str] = {}
    unknown: list[str] = []
    for raw in headers:
        n = normalize_header(raw)
        found = False
        for canonical, aliases in CANONICAL_ALIASES.items():
            alias_norms = {normalize_header(a) for a in aliases}
            if n in alias_norms:
                if canonical not in mapped:
                    mapped[canonical] = raw
                found = True
                break
        if not found:
            unknown.append(raw)

    present = set(mapped.keys())
    missing_by_domain = {
        domain: [f for f in required if f not in present]
        for domain, required in REQUIRED_BY_DOMAIN.items()
    }
    return {
        "mapped_columns": mapped,
        "canonical_present": sorted(present),
        "unknown_columns": unknown,
        "missing_by_domain": missing_by_domain,
    }


def map_dataframe(df: pd.DataFrame, extra_maps: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """Rename columns to canonical names; keep unmapped columns unchanged."""
    if df.empty:
        return df

    aliases = dict(CANONICAL_ALIASES)
    if extra_maps:
        for k, v in extra_maps.items():
            aliases[k] = tuple(list(aliases.get(k, ())) + list(v))

    rename: dict[str, str] = {}
    lower_to_raw = {normalize_header(c): c for c in df.columns}
    used_canonical: set[str] = set()

    for canonical, candidates in aliases.items():
        if canonical in used_canonical:
            continue
        for cand in candidates:
            if cand in df.columns:
                rename[cand] = canonical
                used_canonical.add(canonical)
                break
            norm = normalize_header(cand)
            if norm in lower_to_raw:
                rename[lower_to_raw[norm]] = canonical
                used_canonical.add(canonical)
                break

    out = df.rename(columns=rename)
    # Coerce common numeric columns when present
    for col in ("price", "cost", "revenue", "quantity", "discount_amount", "margin", "on_hand", "stock"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "sold_at" in out.columns:
        out["sold_at"] = pd.to_datetime(out["sold_at"], errors="coerce", utc=True)
    return out


def row_dict(row: pd.Series, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Safe row access — never unpack tuples."""
    keys = fields or tuple(row.index)
    return {k: row[k] if k in row.index else None for k in keys}


def safe_get(row: pd.Series | dict, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return row.get(key, default) if key in row.index else default
