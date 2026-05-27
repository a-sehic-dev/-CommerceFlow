"""
Deterministic inventory classification from uploaded sales, product, and inventory data.

All thresholds are explicit business rules (configurable via Settings).
KPI totals are sums of per-SKU calculated values — never hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.config import Settings

# Business rule constants (defaults mirrored in Settings / .env)
VELOCITY_WINDOW_30D = 30
VELOCITY_WINDOW_90D = 90
DEAD_MIN_DAYS_SINCE_LAST_SALE = 180
DEAD_MAX_VELOCITY_90D = 0.05
SLOW_MOVING_MIN_DAYS_SINCE_LAST_SALE = 60
SLOW_MOVING_MAX_DAYS_SINCE_LAST_SALE = 179
SLOW_MOVING_MAX_VELOCITY_90D = 0.15
OVERSTOCK_MIN_DAYS_COVER = 90
OVERSTOCK_TARGET_DAYS_COVER = 90
LOW_STOCK_MAX_DAYS_COVER = 14
DEAD_INVENTORY_RECOVERY_RATE = 0.25

CLASSIFICATION_DEAD = "dead_inventory"
CLASSIFICATION_SLOW = "slow_moving"
CLASSIFICATION_OVERSTOCK = "overstock"
CLASSIFICATION_LOW_STOCK = "low_stock"
CLASSIFICATION_STOCKOUT = "stockout_risk"
CLASSIFICATION_HEALTHY = "healthy"
CLASSIFICATION_INSUFFICIENT = "insufficient_activity_history"


@dataclass(frozen=True)
class InventoryClassification:
    dead: pd.DataFrame
    slow_moving: pd.DataFrame
    overstock: pd.DataFrame
    low_stock: pd.DataFrame
    stockout_risk: pd.DataFrame
    healthy: pd.DataFrame
    insufficient_activity: pd.DataFrame
    risk_rows: list[dict]
    dead_inventory_value: float
    recoverable_dead_inventory_value: float
    slow_moving_value: float
    overstock_value: float
    healthy_value: float


def sales_velocity_by_sku(
    sales_df: pd.DataFrame,
    *,
    window_days: int,
    as_of: pd.Timestamp,
) -> dict[str, float]:
    """Units per day for each SKU within the trailing window ending at as_of."""
    if sales_df.empty or "sku" not in sales_df.columns:
        return {}

    work = sales_df.copy()
    work["sku"] = work["sku"].astype(str)
    qty = pd.to_numeric(work.get("quantity", 0), errors="coerce").fillna(0)
    work["_qty"] = qty

    if "sold_at" in work.columns:
        work["sold_at"] = pd.to_datetime(work["sold_at"], errors="coerce", utc=True)
        if work["sold_at"].dt.tz is None:
            work["sold_at"] = work["sold_at"].dt.tz_localize("UTC")
        cutoff = as_of - pd.Timedelta(days=window_days)
        work = work[work["sold_at"].notna() & (work["sold_at"] >= cutoff) & (work["sold_at"] <= as_of)]
    elif "aggregated" in work.columns and bool(work["aggregated"].any()):
        total_days = max(window_days, 1)
        vel = work.groupby("sku", as_index=True)["_qty"].sum() / total_days
        return {str(k): float(v) for k, v in vel.to_dict().items()}
    else:
        work = work
        total_days = max(window_days, 1)

    if work.empty:
        return {}

    span_days = window_days
    if "sold_at" in work.columns and work["sold_at"].notna().any():
        span = (work["sold_at"].max() - work["sold_at"].min()).days
        span_days = max(int(span) if pd.notna(span) else 0, 1)
        span_days = min(span_days, window_days)

    vel = work.groupby("sku", as_index=True)["_qty"].sum() / max(span_days, 1)
    return {str(k): float(v) for k, v in vel.to_dict().items()}


def _reference_as_of(sales_df: pd.DataFrame) -> pd.Timestamp:
    if not sales_df.empty and "sold_at" in sales_df.columns:
        sold = pd.to_datetime(sales_df["sold_at"], errors="coerce", utc=True)
        if sold.notna().any():
            return sold.max()
    return pd.Timestamp(datetime.now(timezone.utc))


def _last_sale_dates(sales_df: pd.DataFrame) -> dict[str, pd.Timestamp]:
    if sales_df.empty or "sku" not in sales_df.columns or "sold_at" not in sales_df.columns:
        return {}
    work = sales_df.copy()
    work["sku"] = work["sku"].astype(str)
    work["sold_at"] = pd.to_datetime(work["sold_at"], errors="coerce", utc=True)
    work = work.dropna(subset=["sold_at"])
    if work.empty:
        return {}
    return work.groupby("sku")["sold_at"].max().to_dict()


def normalize_inventory_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "quantity_on_hand" not in out.columns:
        for alias in ("on_hand", "stock", "stock_on_hand", "available_units", "quantity"):
            if alias in out.columns:
                out["quantity_on_hand"] = pd.to_numeric(out[alias], errors="coerce").fillna(0)
                break
        else:
            out["quantity_on_hand"] = 0
    return out


def _product_maps(products_df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    cost_map: dict[str, float] = {}
    price_map: dict[str, float] = {}
    title_map: dict[str, str] = {}
    if products_df.empty or "sku" not in products_df.columns:
        return cost_map, price_map, title_map
    prod = products_df.drop_duplicates("sku").copy()
    prod["sku"] = prod["sku"].astype(str)
    if "cost" in prod.columns:
        cost_map = (
            pd.to_numeric(prod.set_index("sku")["cost"], errors="coerce").fillna(0).astype(float).to_dict()
        )
    if "price" in prod.columns:
        price_map = (
            pd.to_numeric(prod.set_index("sku")["price"], errors="coerce").fillna(0).astype(float).to_dict()
        )
    if "title" in prod.columns:
        title_map = prod.set_index("sku")["title"].astype(str).to_dict()
    return cost_map, price_map, title_map


def _unit_cost(sku: str, cost_map: dict[str, float], price_map: dict[str, float]) -> float:
    cost = float(cost_map.get(sku, 0) or 0)
    if cost > 0:
        return cost
    return float(price_map.get(sku, 0) or 0)


def _thresholds(settings: Settings | None) -> dict[str, float | int]:
    s = settings or Settings()
    return {
        "dead_min_days_since_last_sale": int(getattr(s, "dead_min_days_since_last_sale", DEAD_MIN_DAYS_SINCE_LAST_SALE)),
        "dead_max_velocity_90d": float(getattr(s, "dead_max_velocity_90d", DEAD_MAX_VELOCITY_90D)),
        "slow_moving_min_days_since_last_sale": int(getattr(s, "slow_moving_min_days_since_last_sale", SLOW_MOVING_MIN_DAYS_SINCE_LAST_SALE)),
        "slow_moving_max_days_since_last_sale": int(getattr(s, "slow_moving_max_days_since_last_sale", SLOW_MOVING_MAX_DAYS_SINCE_LAST_SALE)),
        "slow_moving_max_velocity_90d": float(getattr(s, "slow_moving_max_velocity_90d", SLOW_MOVING_MAX_VELOCITY_90D)),
        "overstock_min_days_cover": float(getattr(s, "overstock_min_days_cover", OVERSTOCK_MIN_DAYS_COVER)),
        "overstock_target_days_cover": float(getattr(s, "overstock_target_days_cover", OVERSTOCK_TARGET_DAYS_COVER)),
        "low_stock_max_days_cover": float(getattr(s, "low_stock_max_days_cover", LOW_STOCK_MAX_DAYS_COVER)),
    }


def build_inventory_metrics(
    inventory_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
    settings: Settings | None = None,
) -> pd.DataFrame:
    """Per-SKU metrics used for classification and reporting."""
    thresholds = _thresholds(settings)
    df = normalize_inventory_columns(inventory_df)
    if df.empty:
        return df

    df["sku"] = df["sku"].astype(str)
    df["stock_on_hand"] = pd.to_numeric(df["quantity_on_hand"], errors="coerce").fillna(0).astype(float)
    cost_map, price_map, title_map = _product_maps(products_df)

    as_of = _reference_as_of(sales_df)
    last_sales = _last_sale_dates(sales_df)
    vel_30 = sales_velocity_by_sku(sales_df, window_days=VELOCITY_WINDOW_30D, as_of=as_of)
    vel_90 = sales_velocity_by_sku(sales_df, window_days=VELOCITY_WINDOW_90D, as_of=as_of)

    if "days_in_stock" in df.columns:
        days_in_stock = pd.to_numeric(df["days_in_stock"], errors="coerce")
    else:
        days_in_stock = pd.Series(np.nan, index=df.index, dtype=float)
    days_since_last_sale: list[float | None] = []
    has_sale_history: list[bool] = []
    for sku, age in zip(df["sku"].astype(str), days_in_stock, strict=False):
        if sku in last_sales:
            delta = (as_of - last_sales[sku]).days
            days_since_last_sale.append(float(max(delta, 0)))
            has_sale_history.append(True)
        elif pd.notna(age):
            days_since_last_sale.append(float(age))
            has_sale_history.append(False)
        else:
            days_since_last_sale.append(None)
            has_sale_history.append(False)

    df["product_name"] = df["sku"].map(lambda s: title_map.get(str(s), ""))
    df["unit_cost"] = df["sku"].map(lambda s: _unit_cost(str(s), cost_map, price_map))
    df["sales_velocity_30d"] = df["sku"].map(lambda s: vel_30.get(str(s), 0.0)).astype(float)
    df["sales_velocity_90d"] = df["sku"].map(lambda s: vel_90.get(str(s), 0.0)).astype(float)
    df["days_since_last_sale"] = days_since_last_sale
    df["has_sale_history"] = has_sale_history
    df["inventory_value"] = df["stock_on_hand"] * df["unit_cost"]

    cover: list[float] = []
    for _, row in df.iterrows():
        v90 = float(row["sales_velocity_90d"])
        stock = float(row["stock_on_hand"])
        if v90 > 0 and stock > 0:
            cover.append(stock / v90)
        else:
            cover.append(float("inf") if stock > 0 else 0.0)
    df["days_of_cover"] = cover

    target_units = df["sales_velocity_90d"] * thresholds["overstock_target_days_cover"]
    df["excess_units"] = (df["stock_on_hand"] - target_units).clip(lower=0)
    df["overstock_value"] = df["excess_units"] * df["unit_cost"]
    return df


def _is_dead(row: pd.Series, *, days_known: bool, thresholds: dict) -> tuple[bool, str]:
    if not days_known or row["days_since_last_sale"] is None:
        return False, ""
    days = float(row["days_since_last_sale"])
    stock = float(row["stock_on_hand"])
    v30 = float(row["sales_velocity_30d"])
    v90 = float(row["sales_velocity_90d"])
    inv_val = float(row["inventory_value"])
    dead_days = int(thresholds["dead_min_days_since_last_sale"])
    dead_vel = float(thresholds["dead_max_velocity_90d"])
    if stock <= 0:
        return False, ""
    if days < dead_days:
        return False, ""
    if v30 != 0:
        return False, ""
    if v90 > dead_vel:
        return False, ""
    if inv_val <= 0:
        return False, ""
    return True, (
        f"No sales in {VELOCITY_WINDOW_30D}d; last sale {days:.0f}d ago; "
        f"90d velocity {v90:.3f} u/day (≤{dead_vel}); "
        f"inventory value ${inv_val:,.2f}"
    )


def _is_slow_moving(row: pd.Series, *, days_known: bool, thresholds: dict) -> tuple[bool, str]:
    stock = float(row["stock_on_hand"])
    if stock <= 0:
        return False, ""
    v90 = float(row["sales_velocity_90d"])
    slow_vel = float(thresholds["slow_moving_max_velocity_90d"])
    slow_min = int(thresholds["slow_moving_min_days_since_last_sale"])
    slow_max = int(thresholds["slow_moving_max_days_since_last_sale"])
    by_velocity = 0 < v90 <= slow_vel
    by_aging = False
    if days_known and row["days_since_last_sale"] is not None:
        days = float(row["days_since_last_sale"])
        by_aging = slow_min <= days <= slow_max
    if not (by_velocity or by_aging):
        return False, ""
    reasons = []
    if by_aging:
        reasons.append(
            f"Last sale {float(row['days_since_last_sale']):.0f}d ago "
            f"({slow_min}–{slow_max}d band)"
        )
    if by_velocity:
        reasons.append(f"90d velocity {v90:.3f} u/day (≤{slow_vel})")
    return True, "; ".join(reasons)


def _is_overstock(row: pd.Series, thresholds: dict) -> tuple[bool, str]:
    stock = float(row["stock_on_hand"])
    v90 = float(row["sales_velocity_90d"])
    cover = float(row["days_of_cover"])
    min_cover = float(thresholds["overstock_min_days_cover"])
    target_cover = float(thresholds["overstock_target_days_cover"])
    if stock <= 0 or v90 <= 0:
        return False, ""
    if cover < min_cover:
        return False, ""
    excess = float(row["excess_units"])
    return True, (
        f"{cover:.0f} days of cover (≥{min_cover:.0f}); "
        f"excess {excess:.0f} units above {target_cover:.0f}d target"
    )


def _is_low_stock(row: pd.Series, thresholds: dict) -> tuple[bool, str]:
    stock = float(row["stock_on_hand"])
    v30 = float(row["sales_velocity_30d"])
    cover = float(row["days_of_cover"])
    max_cover = float(thresholds["low_stock_max_days_cover"])
    if stock <= 0 or v30 <= 0:
        return False, ""
    if cover > max_cover:
        return False, ""
    return True, (
        f"{cover:.1f} days of cover (≤{max_cover:.0f}); "
        f"30d velocity {v30:.3f} u/day"
    )


def _is_stockout(row: pd.Series, thresholds: dict) -> tuple[bool, str]:
    _ = thresholds
    stock = float(row["stock_on_hand"])
    v30 = float(row["sales_velocity_30d"])
    if stock > 0 or v30 <= 0:
        return False, ""
    return True, f"Zero on-hand with {VELOCITY_WINDOW_30D}d velocity {v30:.3f} u/day"


def classify_inventory(
    inventory_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
    settings: Settings | None = None,
) -> InventoryClassification:
    empty = inventory_df.iloc[0:0] if not inventory_df.empty else pd.DataFrame()
    if inventory_df.empty:
        return InventoryClassification(
            dead=empty,
            slow_moving=empty,
            overstock=empty,
            low_stock=empty,
            stockout_risk=empty,
            healthy=empty,
            insufficient_activity=empty,
            risk_rows=[],
            dead_inventory_value=0.0,
            recoverable_dead_inventory_value=0.0,
            slow_moving_value=0.0,
            overstock_value=0.0,
            healthy_value=0.0,
        )

    metrics = build_inventory_metrics(inventory_df, sales_df, products_df, settings)
    thresholds = _thresholds(settings)
    classifications: list[str] = []
    reasons: list[str] = []
    risk_rows: list[dict] = []

    for _, row in metrics.iterrows():
        days_known = row["days_since_last_sale"] is not None
        stock = float(row["stock_on_hand"])

        if not days_known and stock > 0 and not row["has_sale_history"]:
            cls = CLASSIFICATION_INSUFFICIENT
            reason = "No sales history and no inventory age — cannot classify as dead stock"
        elif _is_stockout(row, thresholds)[0]:
            cls, reason = CLASSIFICATION_STOCKOUT, _is_stockout(row, thresholds)[1]
        elif _is_dead(row, days_known=days_known, thresholds=thresholds)[0]:
            cls, reason = CLASSIFICATION_DEAD, _is_dead(row, days_known=days_known, thresholds=thresholds)[1]
        elif _is_low_stock(row, thresholds)[0]:
            cls, reason = CLASSIFICATION_LOW_STOCK, _is_low_stock(row, thresholds)[1]
        elif _is_slow_moving(row, days_known=days_known, thresholds=thresholds)[0]:
            cls, reason = CLASSIFICATION_SLOW, _is_slow_moving(row, days_known=days_known, thresholds=thresholds)[1]
        elif _is_overstock(row, thresholds)[0]:
            cls, reason = CLASSIFICATION_OVERSTOCK, _is_overstock(row, thresholds)[1]
        elif stock > 0:
            cls = CLASSIFICATION_HEALTHY
            reason = (
                f"Within targets: {row['days_of_cover']:.0f}d cover, "
                f"90d velocity {float(row['sales_velocity_90d']):.3f} u/day"
            )
        else:
            cls = CLASSIFICATION_INSUFFICIENT
            reason = "No on-hand stock to classify"

        classifications.append(cls)
        reasons.append(reason)
        risk_rows.append(_risk_row_dict(row, cls, reason))

    metrics["classification"] = classifications
    metrics["classification_reason"] = reasons

    dead = metrics[metrics["classification"] == CLASSIFICATION_DEAD]
    slow = metrics[metrics["classification"] == CLASSIFICATION_SLOW]
    over = metrics[metrics["classification"] == CLASSIFICATION_OVERSTOCK]
    low = metrics[metrics["classification"] == CLASSIFICATION_LOW_STOCK]
    stockout = metrics[metrics["classification"] == CLASSIFICATION_STOCKOUT]
    healthy = metrics[metrics["classification"] == CLASSIFICATION_HEALTHY]
    insufficient = metrics[metrics["classification"] == CLASSIFICATION_INSUFFICIENT]

    dead_value = float(dead["inventory_value"].sum()) if not dead.empty else 0.0
    return InventoryClassification(
        dead=dead,
        slow_moving=slow,
        overstock=over,
        low_stock=low,
        stockout_risk=stockout,
        healthy=healthy,
        insufficient_activity=insufficient,
        risk_rows=risk_rows,
        dead_inventory_value=dead_value,
        recoverable_dead_inventory_value=dead_value * DEAD_INVENTORY_RECOVERY_RATE,
        slow_moving_value=float(slow["inventory_value"].sum()) if not slow.empty else 0.0,
        overstock_value=float(over["overstock_value"].sum()) if not over.empty else 0.0,
        healthy_value=float(healthy["inventory_value"].sum()) if not healthy.empty else 0.0,
    )


def _risk_row_dict(row: pd.Series, classification: str, reason: str) -> dict:
    days_sl = row["days_since_last_sale"]
    cover = row["days_of_cover"]
    return {
        "sku": row["sku"],
        "product_name": row.get("product_name", ""),
        "stock_on_hand": int(round(float(row["stock_on_hand"]))),
        "days_since_last_sale": None if days_sl is None else round(float(days_sl), 1),
        "sales_velocity_30d": round(float(row["sales_velocity_30d"]), 4),
        "sales_velocity_90d": round(float(row["sales_velocity_90d"]), 4),
        "days_of_cover": None if cover == float("inf") else round(float(cover), 1),
        "inventory_value": round(float(row["inventory_value"]), 2),
        "unit_cost": round(float(row["unit_cost"]), 2),
        "classification": classification,
        "classification_reason": reason,
        "type": classification,
        "quantity": int(round(float(row["stock_on_hand"]))),
        "quantity_on_hand": int(round(float(row["stock_on_hand"]))),
        "daily_velocity": round(float(row["sales_velocity_90d"]), 4),
        "overstock_value": round(float(row.get("overstock_value", 0) or 0), 2),
    }
