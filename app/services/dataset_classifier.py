"""Classify uploaded datasets from column structure — never from filenames."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.utils.schema_mapper import REQUIRED_BY_DOMAIN, detect_schema, normalize_header

# Signal groups: any alias match counts as one hit (column-header scoring).
SALES_SIGNALS: tuple[tuple[str, ...], ...] = (
    ("order_id", "order_number", "order_no", "order #", "orderid", "transaction_id", "invoice_id"),
    (
        "revenue",
        "total_revenue",
        "line_total",
        "total",
        "sales_amount",
        "gross_sales",
        "net_sales",
        "amount",
        "order_total",
    ),
    ("quantity", "qty", "units_sold", "units", "item_quantity", "ordered_qty", "shipped_qty"),
    (
        "sold_at",
        "order_date",
        "sale_date",
        "created_at",
        "date",
        "timestamp",
        "transaction_date",
        "purchase_date",
    ),
    ("customer", "customer_name", "customer_id", "buyer", "email", "bill_to", "ship_to_name"),
    ("sales_channel", "channel", "source", "marketplace", "platform", "store", "region"),
    ("discount_amount", "discount", "discounts", "line_discount", "promo"),
    ("sku", "item_sku", "product_sku", "variant_sku"),
)

PRODUCTS_SIGNALS: tuple[tuple[str, ...], ...] = (
    ("product_name", "title", "name", "product", "item_name", "description", "item_description"),
    ("sku", "variant_sku", "product_sku", "item_sku", "code", "product_code", "item_code"),
    ("category", "product_category", "type", "collection", "product_type", "department"),
    ("unit_price", "price", "retail_price", "variant_price", "regular_price", "msrp", "list_price"),
    ("cost", "unit_cost", "cogs", "landed_cost"),
    ("margin", "margin_pct", "profit_margin", "gross_margin"),
    ("status", "product_status", "active", "published", "visibility"),
    ("vendor", "brand", "manufacturer", "supplier"),
)

INVENTORY_SIGNALS: tuple[tuple[str, ...], ...] = (
    ("warehouse", "location", "fulfillment_center", "store", "bin", "site", "dc"),
    (
        "on_hand",
        "quantity_on_hand",
        "qty_on_hand",
        "stock_on_hand",
        "inventory_qty",
        "stock_level",
        "qty_available",
    ),
    ("available_units", "available", "available_stock", "free_stock", "sellable", "ats"),
    ("reserved", "quantity_reserved", "reserved_qty", "committed", "allocated"),
    ("inbound", "incoming", "on_order", "po_quantity", "expected"),
    ("stock", "quantity", "qty", "inventory", "units_on_hand", "days_in_stock"),
    ("sku", "item_sku", "product_sku"),
    ("days_in_stock", "days_in_inventory", "aging_days", "age_days", "stock_age"),
)

# Canonical fields used for schema-domain scoring (from mapped headers).
SCHEMA_DOMAIN_FIELDS: dict[str, frozenset[str]] = {
    "sales": frozenset(
        {"order_id", "revenue", "quantity", "sold_at", "customer", "sales_channel", "discount_amount", "sku"}
    ),
    "products": frozenset({"sku", "title", "price", "category", "cost", "margin", "status", "vendor"}),
    "inventory": frozenset(
        {"sku", "on_hand", "available_units", "reserved", "inbound", "stock", "warehouse", "days_in_stock"}
    ),
}

CONFIDENCE_HIGH = 0.5
CONFIDENCE_MIN = 0.34
CONFIDENCE_GAP = 0.17


@dataclass
class ClassificationResult:
    primary_type: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    matched_signals: dict[str, list[str]] = field(default_factory=dict)
    needs_confirmation: bool = False
    reason: str = ""
    method: str = "headers"
    schema_present: list[str] = field(default_factory=list)

    @property
    def is_confident(self) -> bool:
        return (
            not self.needs_confirmation
            and self.primary_type in ("sales", "products", "inventory")
        )

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "scores": self.scores,
            "matched_signals": self.matched_signals,
            "reason": self.reason,
            "method": self.method,
            "schema_present": self.schema_present,
            "primary_type": self.primary_type,
            "needs_confirmation": self.needs_confirmation,
        }


def _header_set(headers: list[str]) -> set[str]:
    return {normalize_header(h) for h in headers}


def _has_any(norm: set[str], aliases: tuple[str, ...]) -> bool:
    return any(normalize_header(a) in norm for a in aliases)


def _match_groups(headers: list[str], groups: tuple[tuple[str, ...], ...]) -> tuple[int, list[str]]:
    norm = _header_set(headers)
    matched_labels: list[str] = []
    hits = 0
    for group in groups:
        for alias in group:
            if normalize_header(alias) in norm:
                hits += 1
                matched_labels.append(group[0])
                break
    return hits, matched_labels


def _has_sales_fingerprint(headers: list[str]) -> bool:
    norm = _header_set(headers)
    return (
        _has_any(norm, ("order_id", "order_number", "order_no", "transaction_id", "invoice_id"))
        and _has_any(
            norm,
            ("sold_at", "order_date", "sale_date", "created_at", "date", "transaction_date"),
        )
        and _has_any(
            norm,
            ("revenue", "line_total", "sales_amount", "total", "net_sales", "gross_sales", "amount"),
        )
    )


def _has_products_fingerprint(headers: list[str]) -> bool:
    norm = _header_set(headers)
    return _has_any(
        norm, ("title", "product_name", "name", "product", "item_name", "item_description")
    ) and _has_any(norm, ("price", "unit_price", "retail_price", "list_price", "msrp"))


def _has_inventory_fingerprint(headers: list[str]) -> bool:
    norm = _header_set(headers)
    stock = _has_any(
        norm,
        (
            "on_hand",
            "quantity_on_hand",
            "stock",
            "available_units",
            "quantity",
            "stock_level",
            "qty_on_hand",
        ),
    )
    wh = _has_any(norm, ("warehouse", "location", "fulfillment_center", "site", "dc"))
    aging = _has_any(norm, ("days_in_stock", "days_in_inventory", "aging_days", "stock_age"))
    sku_only_inv = _has_any(norm, ("sku", "item_sku")) and stock and not _has_sales_fingerprint(headers)
    return (stock and (wh or aging)) or sku_only_inv


def _score_from_schema(schema: dict[str, Any]) -> tuple[dict[str, float], list[str], dict[str, list[str]]]:
    present = set(schema.get("canonical_present") or [])
    missing_by_domain = schema.get("missing_by_domain") or {}
    totals = {k: max(len(v), 1) for k, v in SCHEMA_DOMAIN_FIELDS.items()}
    matched: dict[str, list[str]] = {k: [] for k in SCHEMA_DOMAIN_FIELDS}

    scores: dict[str, float] = {}
    for domain, fields in SCHEMA_DOMAIN_FIELDS.items():
        hit_fields = [f for f in fields if f in present]
        matched[domain] = hit_fields
        base = len(hit_fields) / len(fields) if fields else 0.0
        required = REQUIRED_BY_DOMAIN.get(domain, ())
        if required:
            missing = missing_by_domain.get(domain) or []
            if not missing and all(r in present for r in required):
                base = max(base, CONFIDENCE_HIGH)
            elif missing:
                base *= 0.65
        scores[domain] = round(base, 3)

    return scores, sorted(present), matched


def _merge_scores(*score_dicts: dict[str, float]) -> dict[str, float]:
    keys = ("sales", "products", "inventory")
    merged: dict[str, float] = {k: 0.0 for k in keys}
    weights = [0.55, 0.45] if len(score_dicts) == 2 else [1.0]
    for weight, scores in zip(weights, score_dicts):
        for k in keys:
            merged[k] += scores.get(k, 0.0) * weight
    return {k: round(v, 3) for k, v in merged.items()}


def _merge_matched(*matched_dicts: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"sales": [], "products": [], "inventory": []}
    for md in matched_dicts:
        for k, vals in md.items():
            for v in vals:
                if v not in out[k]:
                    out[k].append(v)
    return out


def _decide_type(
    scores: dict[str, float],
    matched: dict[str, list[str]],
    headers: list[str],
    *,
    declared_type: str | None = None,
    method: str = "headers",
    schema_present: list[str] | None = None,
) -> ClassificationResult:
    if declared_type in ("products", "sales", "inventory"):
        label = type_label(declared_type)
        return ClassificationResult(
            primary_type=declared_type,
            confidence=1.0,
            scores=scores,
            matched_signals=matched,
            needs_confirmation=False,
            reason=f"Dataset type explicitly set to {label} (user override).",
            method="user_override",
            schema_present=schema_present or [],
        )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    needs_confirmation = False

    if top_score < CONFIDENCE_MIN:
        primary = "unknown"
        needs_confirmation = True
    elif top_score < CONFIDENCE_HIGH or (top_score - second_score) < CONFIDENCE_GAP:
        if top_score >= CONFIDENCE_MIN and second_score >= CONFIDENCE_MIN:
            primary = "mixed"
        needs_confirmation = True
    elif scores["sales"] >= CONFIDENCE_MIN and scores["products"] >= CONFIDENCE_MIN:
        primary = "mixed"
        needs_confirmation = True

    if _has_sales_fingerprint(headers) and scores["sales"] >= CONFIDENCE_MIN:
        primary = "sales"
        needs_confirmation = False
    elif _has_products_fingerprint(headers) and scores["products"] >= CONFIDENCE_MIN:
        primary = "products"
        needs_confirmation = False
    elif _has_inventory_fingerprint(headers) and scores["inventory"] >= CONFIDENCE_MIN:
        primary = "inventory"
        needs_confirmation = False

    reason = _build_reason(primary, scores, matched, needs_confirmation, method)
    return ClassificationResult(
        primary_type=primary,
        confidence=round(top_score, 3),
        scores=scores,
        matched_signals=matched,
        needs_confirmation=needs_confirmation,
        reason=reason,
        method=method,
        schema_present=schema_present or [],
    )


def _build_reason(
    primary: str,
    scores: dict[str, float],
    matched: dict[str, list[str]],
    needs_confirmation: bool,
    method: str,
) -> str:
    parts = [
        f"Classified as {type_label(primary)} via {method.replace('_', ' ')}.",
        (
            "Scores — "
            f"Sales: {scores.get('sales', 0):.0%}, "
            f"Products: {scores.get('products', 0):.0%}, "
            f"Inventory: {scores.get('inventory', 0):.0%}."
        ),
    ]
    for domain in ("sales", "products", "inventory"):
        hits = matched.get(domain) or []
        if hits:
            parts.append(f"{type_label(domain)} signals: {', '.join(hits[:6])}.")
    if needs_confirmation:
        parts.append("Confidence is low or multiple dataset types match — please confirm the type.")
    return " ".join(parts)


def classify_headers(headers: list[str]) -> ClassificationResult:
    """Score dataset type from raw or mapped column headers."""
    sales_hits, sales_m = _match_groups(headers, SALES_SIGNALS)
    products_hits, products_m = _match_groups(headers, PRODUCTS_SIGNALS)
    inv_hits, inv_m = _match_groups(headers, INVENTORY_SIGNALS)

    scores = {
        "sales": sales_hits / len(SALES_SIGNALS),
        "products": products_hits / len(PRODUCTS_SIGNALS),
        "inventory": inv_hits / len(INVENTORY_SIGNALS),
    }
    matched = {"sales": sales_m, "products": products_m, "inventory": inv_m}
    return _decide_type(scores, matched, headers, method="column_headers")


def classify_from_schema(schema: dict[str, Any]) -> ClassificationResult:
    """Score dataset type from canonical schema mapping of headers."""
    scores, present, matched = _score_from_schema(schema)
    headers = list(schema.get("mapped_columns", {}).values()) + list(schema.get("unknown_columns") or [])
    return _decide_type(
        scores,
        matched,
        headers,
        method="schema_mapping",
        schema_present=present,
    )


def classify_dataset(
    headers: list[str],
    *,
    schema: dict[str, Any] | None = None,
    declared_type: str | None = None,
) -> ClassificationResult:
    """
    Primary detection entry: combine header signals and schema mapping.
    Filenames are intentionally ignored.
    """
    if declared_type in ("products", "sales", "inventory"):
        header_result = classify_headers(headers)
        return _decide_type(
            header_result.scores,
            header_result.matched_signals,
            headers,
            declared_type=declared_type,
            method="user_override",
            schema_present=(schema or {}).get("canonical_present") or [],
        )

    header_result = classify_headers(headers)
    if schema is None:
        schema = detect_schema(headers)

    schema_result = classify_from_schema(schema)
    merged_scores = _merge_scores(header_result.scores, schema_result.scores)
    merged_matched = _merge_matched(header_result.matched_signals, schema_result.matched_signals)
    present = sorted(set((schema or {}).get("canonical_present") or []) | set(schema_result.schema_present))

    return _decide_type(
        merged_scores,
        merged_matched,
        headers,
        method="column_headers+schema",
        schema_present=present,
    )


def infer_importer_flags(
    mapped_columns: list[str],
    import_type: str,
    classification: ClassificationResult | None = None,
) -> dict[str, bool]:
    """Decide which importers to run from resolved type, classification, and mapped columns."""
    cols = set(mapped_columns)
    if import_type == "products":
        return {"products": True, "sales": False, "inventory": False}
    if import_type == "sales":
        return {"products": False, "sales": True, "inventory": False}
    if import_type == "inventory":
        return {"products": False, "sales": False, "inventory": True}
    if import_type == "mixed":
        has_products = "sku" in cols and ("title" in cols or "price" in cols or "unit_price" in cols)
        has_sales = "sold_at" in cols or "order_id" in cols or (
            "revenue" in cols and "title" not in cols
        )
        has_inventory = ("on_hand" in cols or "stock" in cols or "quantity" in cols) and (
            "warehouse" in cols or "days_in_stock" in cols or not has_products
        )
        return {"products": has_products, "sales": has_sales, "inventory": has_inventory}

    if classification and classification.primary_type in ("products", "sales", "inventory"):
        if not classification.needs_confirmation or classification.confidence >= CONFIDENCE_MIN:
            t = classification.primary_type
            return {
                "products": t == "products",
                "sales": t == "sales",
                "inventory": t == "inventory",
            }

    # Column-structure fallback (no filename heuristics)
    has_products = "sku" in cols and "title" in cols
    has_sales = "revenue" in cols or "order_id" in cols or ("quantity" in cols and "sold_at" in cols)
    has_inventory = ("on_hand" in cols or "stock" in cols) and ("sku" in cols or "warehouse" in cols)
    if has_sales and not has_products and not has_inventory:
        return {"products": False, "sales": True, "inventory": False}
    if has_inventory and not has_sales and not has_products:
        return {"products": False, "sales": False, "inventory": True}
    if has_products and not has_sales and not has_inventory:
        return {"products": True, "sales": False, "inventory": False}
    return {
        "products": has_products,
        "sales": has_sales,
        "inventory": has_inventory,
    }


def type_label(dtype: str) -> str:
    return {
        "sales": "Sales Dataset",
        "products": "Products Dataset",
        "inventory": "Inventory Dataset",
        "mixed": "Mixed Dataset",
        "unknown": "Unknown",
    }.get(dtype, dtype.title())
