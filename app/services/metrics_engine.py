"""Dashboard KPIs computed only from selected import datasets."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.config import get_settings
from app.schemas.analytics import DashboardMetrics
from app.utils.metric_trace import metric_trace
from app.utils.scoring import clamp, enterprise_decimal, map_to_band, weighted_score


class MetricsEngine:
    TARGET_MARGIN_PCT = 25.0

    @classmethod
    def compute(
        cls,
        products_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        analysis: dict[str, Any],
        selection: dict[str, int | None],
    ) -> tuple[DashboardMetrics, dict[str, dict]]:
        traces: dict[str, dict] = {}
        settings = get_settings()

        total_revenue, traces["total_revenue"] = cls._total_revenue(sales_df, selection)
        total_orders, traces["total_orders"] = cls._total_orders(sales_df, selection)
        avg_order_value, traces["avg_order_value"] = cls._avg_order_value(
            sales_df, selection, total_revenue, total_orders
        )
        gross_margin_pct, traces["gross_margin_pct"] = cls._gross_margin(
            products_df, sales_df, selection, total_revenue
        )
        product_count, traces["product_count"] = cls._product_count(products_df, selection)
        inventory_efficiency, traces["inventory_efficiency"] = cls._inventory_efficiency(
            inventory_df, sales_df, analysis, selection
        )
        operational_risk, traces["operational_risk_score"] = cls._operational_risk(
            analysis, selection, total_revenue, inventory_df
        )
        dead_inventory_value, traces["dead_inventory_value"] = cls._dead_inventory_value(
            analysis, selection
        )
        profit_leakage, traces["profit_leakage_estimate"] = cls._profit_leakage(
            analysis, selection, total_revenue
        )
        active_alerts, traces["active_alerts"] = cls._active_alerts(analysis, selection)

        return (
            DashboardMetrics(
                total_revenue=total_revenue,
                total_orders=total_orders,
                avg_order_value=avg_order_value,
                gross_margin_pct=gross_margin_pct,
                inventory_efficiency=inventory_efficiency,
                operational_risk_score=operational_risk,
                active_alerts=active_alerts,
                product_count=product_count,
                dead_inventory_value=dead_inventory_value,
                profit_leakage_estimate=profit_leakage,
            ),
            traces,
        )

    @staticmethod
    def _sales_selected(selection: dict) -> bool:
        return bool(selection.get("sales_import_id"))

    @staticmethod
    def _products_selected(selection: dict) -> bool:
        return bool(selection.get("products_import_id"))

    @staticmethod
    def _inventory_selected(selection: dict) -> bool:
        return bool(selection.get("inventory_import_id"))

    @classmethod
    def _total_revenue(cls, sales_df: pd.DataFrame, selection: dict) -> tuple[float | None, dict]:
        if not cls._sales_selected(selection):
            return None, metric_trace(
                "SUM(sales.revenue)",
                "sales",
                0,
                None,
                missing_columns=["sales dataset not selected"],
                notes="Select a sales import to calculate revenue",
            )
        if sales_df.empty or "revenue" not in sales_df.columns:
            return None, metric_trace(
                "SUM(sales.revenue)",
                "sales",
                len(sales_df),
                None,
                columns_used=["revenue"] if "revenue" in sales_df.columns else [],
                missing_columns=[] if "revenue" in sales_df.columns else ["revenue"],
            )
        value = round(float(sales_df["revenue"].sum()), 2)
        return value, metric_trace(
            "SUM(sales.revenue)",
            "sales",
            len(sales_df),
            value,
            columns_used=["revenue"],
        )

    @classmethod
    def _total_orders(cls, sales_df: pd.DataFrame, selection: dict) -> tuple[int | None, dict]:
        if not cls._sales_selected(selection):
            return None, metric_trace(
                "COUNT(DISTINCT order_id) OR COUNT(sales rows)",
                "sales",
                0,
                None,
                notes="Sales dataset not selected",
            )
        if sales_df.empty:
            return 0, metric_trace("COUNT(sales rows)", "sales", 0, 0)
        if "order_id" in sales_df.columns and sales_df["order_id"].notna().any():
            value = int(sales_df["order_id"].nunique())
            return value, metric_trace(
                "COUNT(DISTINCT sales.order_id)",
                "sales",
                len(sales_df),
                value,
                columns_used=["order_id"],
            )
        value = len(sales_df)
        return value, metric_trace(
            "COUNT(sales rows) — order_id column unavailable",
            "sales",
            len(sales_df),
            value,
            columns_used=list(sales_df.columns),
            notes="Used row count because order_id is missing",
        )

    @classmethod
    def _avg_order_value(
        cls,
        sales_df: pd.DataFrame,
        selection: dict,
        total_revenue: float | None,
        total_orders: int | None,
    ) -> tuple[float | None, dict]:
        if total_revenue is None or total_orders is None:
            return None, metric_trace(
                "SUM(revenue) / COUNT(orders)",
                "sales",
                len(sales_df),
                None,
                notes="Requires total revenue and order count",
            )
        if total_orders == 0:
            return None, metric_trace(
                "SUM(revenue) / COUNT(orders)",
                "sales",
                len(sales_df),
                None,
                notes="No orders in selected sales dataset",
            )
        value = round(total_revenue / total_orders, 2)
        return value, metric_trace(
            "SUM(revenue) / COUNT(orders)",
            "sales",
            len(sales_df),
            value,
            columns_used=["revenue", "order_id"],
        )

    @classmethod
    def _gross_margin(
        cls,
        products_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        selection: dict,
        total_revenue: float | None,
    ) -> tuple[float | None, dict]:
        if not cls._products_selected(selection) or not cls._sales_selected(selection):
            return None, metric_trace(
                "SUM(revenue * margin_pct) / SUM(revenue)",
                "products+sales",
                0,
                None,
                notes="Requires both products and sales datasets",
            )
        if products_df.empty or sales_df.empty or total_revenue in (None, 0):
            return None, metric_trace(
                "SUM(revenue * margin_pct) / SUM(revenue)",
                "products+sales",
                len(sales_df),
                None,
                missing_columns=["revenue"] if sales_df.empty else [],
            )

        margin_col = None
        if "margin_pct" in products_df.columns and products_df["margin_pct"].notna().any():
            margin_col = "margin_pct"
        elif "cost" in products_df.columns and "price" in products_df.columns:
            products_df = products_df.copy()
            products_df["margin_pct"] = (
                (products_df["price"] - products_df["cost"])
                / products_df["price"].replace(0, pd.NA)
            ) * 100
            margin_col = "margin_pct"

        if not margin_col:
            return None, metric_trace(
                "SUM(revenue * margin_pct) / SUM(revenue)",
                "products",
                len(products_df),
                None,
                missing_columns=["margin_pct", "cost", "price"],
            )

        margins = products_df.set_index("sku")["margin_pct"].to_dict()
        sales = sales_df.copy()
        sales["margin_pct"] = sales["sku"].map(margins)
        valid = sales[sales["margin_pct"].notna()]
        if valid.empty:
            return None, metric_trace(
                "SUM(revenue * margin_pct) / SUM(revenue)",
                "products+sales",
                len(sales_df),
                None,
                notes="No overlapping SKU margin data",
            )

        weighted = float((valid["revenue"] * valid["margin_pct"]).sum())
        rev = float(valid["revenue"].sum())
        value = enterprise_decimal(weighted / rev, 1) if rev else None
        return value, metric_trace(
            "SUM(revenue * margin_pct) / SUM(revenue)",
            "products+sales",
            len(valid),
            value,
            columns_used=["sku", "revenue", "margin_pct"],
        )

    @classmethod
    def _product_count(cls, products_df: pd.DataFrame, selection: dict) -> tuple[int | None, dict]:
        if not cls._products_selected(selection):
            return None, metric_trace(
                "COUNT(products.sku)",
                "products",
                0,
                None,
                notes="Products dataset not selected",
            )
        value = int(len(products_df))
        return value, metric_trace(
            "COUNT(products rows)",
            "products",
            value,
            value,
            columns_used=["sku"] if "sku" in products_df.columns else list(products_df.columns),
        )

    @classmethod
    def _inventory_efficiency(
        cls,
        inventory_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        analysis: dict,
        selection: dict,
    ) -> tuple[float | None, dict]:
        if not cls._inventory_selected(selection):
            return None, metric_trace(
                "band(turnover, days_cover, dead_ratio) → 68–86%",
                "inventory",
                0,
                None,
                notes="Inventory dataset not selected",
            )
        if inventory_df.empty:
            return None, metric_trace("band(turnover, days_cover, dead_ratio)", "inventory", 0, None)

        inv_summary = analysis.get("inventory_risk", {}).get("summary", {})
        n_skus = max(len(inventory_df), 1)
        dead_count = int(inv_summary.get("dead_inventory_count", 0))
        dead_ratio = dead_count / n_skus

        turnover_signal = cls._stock_turnover_signal(inventory_df, sales_df)
        cover_signal = cls._days_of_cover_signal(inventory_df, sales_df)
        dead_signal = clamp((1.0 - dead_ratio) * 100.0)

        composite = weighted_score(
            [
                (turnover_signal, 0.35),
                (cover_signal, 0.40),
                (dead_signal, 0.25),
            ]
        )
        value = enterprise_decimal(map_to_band(composite, low=35, high=88, out_min=68.0, out_max=86.0), 1)
        value = clamp(value, 68.0, 86.0)
        return value, metric_trace(
            "68–86% band: 35% stock turnover, 40% days-of-cover, 25% (1 − dead SKU ratio)",
            "inventory",
            len(inventory_df),
            value,
            columns_used=["quantity_on_hand", "days_in_stock", "sku"],
        )

    @classmethod
    def _stock_turnover_signal(cls, inventory_df: pd.DataFrame, sales_df: pd.DataFrame) -> float:
        on_hand = (
            float(pd.to_numeric(inventory_df["quantity_on_hand"], errors="coerce").fillna(0).sum())
            if "quantity_on_hand" in inventory_df.columns
            else float(len(inventory_df))
        )
        sold = 0.0
        if not sales_df.empty:
            if "quantity" in sales_df.columns:
                sold = float(pd.to_numeric(sales_df["quantity"], errors="coerce").fillna(0).sum())
            else:
                sold = float(len(sales_df))
        turns = sold / max(on_hand, 1.0)
        return clamp(turns / 2.8 * 100.0, 12.0, 96.0)

    @classmethod
    def _days_of_cover_signal(cls, inventory_df: pd.DataFrame, sales_df: pd.DataFrame) -> float:
        if inventory_df.empty or sales_df.empty or "sku" not in sales_df.columns:
            return 72.0
        velocity: dict[str, float] = {}
        work = sales_df.copy()
        work["sku"] = work["sku"].astype(str)
        if "quantity" in work.columns:
            grp = work.groupby("sku")["quantity"].sum()
        else:
            grp = work.groupby("sku").size()
        days_span = 90.0
        if "sold_at" in work.columns and work["sold_at"].notna().any():
            try:
                sold = pd.to_datetime(work["sold_at"], errors="coerce")
                span = (sold.max() - sold.min()).days
                if span and span > 0:
                    days_span = float(span)
            except (TypeError, ValueError):
                pass
        velocity = (grp / max(days_span, 1.0)).to_dict()

        covers: list[float] = []
        inv = inventory_df.copy()
        inv["sku"] = inv["sku"].astype(str)
        qty = pd.to_numeric(inv.get("quantity_on_hand", 0), errors="coerce").fillna(0)
        for sku, q in zip(inv["sku"], qty):
            v = velocity.get(str(sku), 0.0)
            if v > 0 and q > 0:
                covers.append(float(q) / v)
        if not covers:
            days = pd.to_numeric(inv.get("days_in_stock", 45), errors="coerce").fillna(45)
            median_cover = float(days.median())
        else:
            median_cover = float(pd.Series(covers).median())
        # Target ~32 days cover; wider cover reduces score smoothly
        return clamp(100.0 - abs(median_cover - 32.0) * 1.15, 28.0, 94.0)

    @classmethod
    def _operational_risk(
        cls,
        analysis: dict,
        selection: dict,
        total_revenue: float | None,
        inventory_df: pd.DataFrame,
    ) -> tuple[float | None, dict]:
        profit = analysis.get("profit_leakage", {})
        inv_block = analysis.get("inventory_risk", {})
        inv = inv_block.get("summary", {})
        alerts = inv_block.get("alerts", [])
        issues = profit.get("issues", [])

        if not any([selection.get("products_import_id"), selection.get("sales_import_id")]):
            return None, metric_trace(
                "severity-weighted band → 72–89 (critical, dead stock, low margin, stockout)",
                "analysis",
                0,
                None,
                notes="Requires at least products or sales selection",
            )

        n_skus = max(len(inventory_df), int(inv.get("dead_inventory_count", 0) + inv.get("low_stock_count", 0) + 1))
        critical_alerts = int(profit.get("critical_count", 0)) + sum(
            1 for a in alerts if a.get("severity") == "critical"
        )
        stockout_count = sum(1 for a in alerts if a.get("type") == "stockout_risk")
        dead_count = int(inv.get("dead_inventory_count", 0))
        low_margin_count = sum(1 for i in issues if i.get("type") == "low_margin")

        leakage_ratio = 0.0
        if total_revenue and total_revenue > 0:
            leakage_ratio = float(profit.get("total_estimated_leakage", 0) or 0) / total_revenue

        pressure = weighted_score(
            [
                (min(critical_alerts / 10.0, 1.0) * 100.0, 0.30),
                (min(dead_count / max(n_skus, 1) / 0.22, 1.0) * 100.0, 0.28),
                (min(low_margin_count / 35.0, 1.0) * 100.0, 0.22),
                (min(stockout_count / 18.0, 1.0) * 100.0, 0.20),
            ]
        )
        pressure = min(pressure + leakage_ratio * 18.0, 100.0)
        value = map_to_band(pressure, low=38.0, high=82.0, out_min=72.0, out_max=89.0)
        value = enterprise_decimal(value, 1)
        value = clamp(value, 71.0, 90.0)
        return value, metric_trace(
            "72–89 band: 30% critical alerts, 28% dead inventory, 22% low margin, 20% stockout (+ leakage adj.)",
            "analysis",
            critical_alerts + stockout_count + low_margin_count,
            value,
        )

    @classmethod
    def _dead_inventory_value(cls, analysis: dict, selection: dict) -> tuple[float | None, dict]:
        if not cls._inventory_selected(selection):
            return None, metric_trace(
                "SUM(price * qty) for dead stock SKUs",
                "inventory+products",
                0,
                None,
                notes="Inventory dataset not selected",
            )
        value = analysis.get("inventory_risk", {}).get("summary", {}).get("dead_inventory_value")
        if value is None:
            return None, metric_trace(
                "SUM(price * qty) for dead stock SKUs",
                "inventory_risk",
                0,
                None,
            )
        return float(value), metric_trace(
            "SUM(product.price * inventory.quantity_on_hand) WHERE days_in_stock >= dead_threshold",
            "inventory_risk",
            int(analysis.get("inventory_risk", {}).get("summary", {}).get("dead_inventory_count", 0)),
            value,
        )

    @classmethod
    def _profit_leakage(
        cls, analysis: dict, selection: dict, total_revenue: float | None
    ) -> tuple[float | None, dict]:
        profit = analysis.get("profit_leakage", {})
        if not selection.get("sales_import_id") and not selection.get("products_import_id"):
            return None, metric_trace(
                "capped SUM(weighted issue impacts)",
                "profit_leakage",
                0,
                None,
                notes="Requires products or sales dataset",
            )
        value = profit.get("total_estimated_leakage")
        if value is None:
            return None, metric_trace("capped SUM(weighted issue impacts)", "profit_leakage", 0, None)
        value = round(abs(float(value)), 2)
        traces_detail = profit.get("metric_traces", {})
        return value, metric_trace(
            traces_detail.get("total_formula", "MIN(SUM(weighted impacts), revenue * 0.15, revenue)"),
            "profit_leakage",
            profit.get("issue_count", 0),
            value,
            notes=traces_detail.get("cap_note"),
        )

    @classmethod
    def _active_alerts(cls, analysis: dict, selection: dict) -> tuple[int | None, dict]:
        profit_n = len(analysis.get("profit_leakage", {}).get("issues", []))
        inv_n = len(analysis.get("inventory_risk", {}).get("alerts", []))
        data_n = len(analysis.get("data_cleaning", {}).get("issues", []))
        value = profit_n + inv_n + data_n
        return value, metric_trace(
            "COUNT(profit issues) + COUNT(inventory alerts) + COUNT(data quality issues)",
            "analysis",
            value,
            value,
        )
