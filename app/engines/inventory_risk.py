import pandas as pd

from app.config import get_settings
from app.utils.dataframe_ops import top_n_issues
from app.utils.inventory_classification import (
    CLASSIFICATION_DEAD,
    CLASSIFICATION_HEALTHY,
    CLASSIFICATION_INSUFFICIENT,
    CLASSIFICATION_LOW_STOCK,
    CLASSIFICATION_OVERSTOCK,
    CLASSIFICATION_SLOW,
    CLASSIFICATION_STOCKOUT,
    classify_inventory,
)
from app.utils.scoring import clamp, severity_from_score

_CLASSIFICATION_SCORES = {
    CLASSIFICATION_STOCKOUT: 88,
    CLASSIFICATION_DEAD: 90,
    CLASSIFICATION_LOW_STOCK: 85,
    CLASSIFICATION_OVERSTOCK: 60,
    CLASSIFICATION_SLOW: 72,
    CLASSIFICATION_INSUFFICIENT: 50,
    CLASSIFICATION_HEALTHY: 25,
}

_CLASSIFICATION_RECOMMENDATIONS = {
    CLASSIFICATION_STOCKOUT: "Reorder before stockout",
    CLASSIFICATION_DEAD: "Consider liquidation or write-down",
    CLASSIFICATION_LOW_STOCK: "Restock immediately",
    CLASSIFICATION_OVERSTOCK: "Reduce purchase orders",
    CLASSIFICATION_SLOW: "Run promotions or channel clearance",
    CLASSIFICATION_INSUFFICIENT: "Import sales history or last-sale dates",
    CLASSIFICATION_HEALTHY: "Maintain current replenishment",
}

_CLASSIFICATION_HEALTH = {
    CLASSIFICATION_STOCKOUT: "critical",
    CLASSIFICATION_DEAD: "critical",
    CLASSIFICATION_LOW_STOCK: "high",
    CLASSIFICATION_OVERSTOCK: "medium",
    CLASSIFICATION_SLOW: "medium",
    CLASSIFICATION_INSUFFICIENT: "medium",
    CLASSIFICATION_HEALTHY: "low",
}


class InventoryRiskEngine:
    """Inventory health, classification, and reorder intelligence."""

    def analyze(self, inventory_df: pd.DataFrame, sales_df: pd.DataFrame, products_df: pd.DataFrame) -> dict:
        settings = get_settings()
        if inventory_df.empty:
            return self._empty_result()

        classified = classify_inventory(inventory_df, sales_df, products_df, settings)
        parts = [
            classified.dead,
            classified.slow_moving,
            classified.overstock,
            classified.low_stock,
            classified.stockout_risk,
            classified.healthy,
            classified.insufficient_activity,
        ]
        non_empty = [p for p in parts if not p.empty]
        df = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame(classified.risk_rows)
        if df.empty:
            df = pd.DataFrame(columns=["sku", "classification"])

        df["inventory_health_score"] = df.get("classification", "").map(
            lambda c: round(100 - _CLASSIFICATION_SCORES.get(c, 40), 1)
        )
        df["risk_level"] = df.get("classification", "").map(
            lambda c: _CLASSIFICATION_HEALTH.get(c, "medium")
        )

        alerts = self._alerts_from_risk_rows(classified.risk_rows, settings.analytics_issue_cap)
        reorder = self._reorder_suggestions(classified.risk_rows)

        return {
            "inventory": df,
            "risk_rows": classified.risk_rows,
            "alerts": top_n_issues(alerts, settings.analytics_issue_cap),
            "reorder_suggestions": reorder,
            "summary": {
                "avg_health_score": float(df["inventory_health_score"].mean()) if "inventory_health_score" in df.columns and len(df) else 0,
                "low_stock_count": int(len(classified.low_stock)),
                "overstock_count": int(len(classified.overstock)),
                "slow_moving_count": int(len(classified.slow_moving)),
                "dead_inventory_count": int(len(classified.dead)),
                "healthy_count": int(len(classified.healthy)),
                "insufficient_activity_count": int(len(classified.insufficient_activity)),
                "dead_inventory_value": round(classified.dead_inventory_value, 2),
                "recoverable_dead_inventory_value": round(classified.recoverable_dead_inventory_value, 2),
                "slow_moving_value": round(classified.slow_moving_value, 2),
                "overstock_value": round(classified.overstock_value, 2),
                "healthy_inventory_value": round(classified.healthy_value, 2),
            },
        }

    def _alerts_from_risk_rows(self, risk_rows: list[dict], cap: int) -> list[dict]:
        alert_types = {
            CLASSIFICATION_STOCKOUT,
            CLASSIFICATION_DEAD,
            CLASSIFICATION_LOW_STOCK,
            CLASSIFICATION_OVERSTOCK,
            CLASSIFICATION_SLOW,
            CLASSIFICATION_INSUFFICIENT,
        }
        out: list[dict] = []
        for row in risk_rows:
            cls = row.get("classification") or row.get("type")
            if cls not in alert_types:
                continue
            score = _CLASSIFICATION_SCORES.get(cls, 60)
            sku = row.get("sku", "")
            out.append({
                "type": cls,
                "sku": sku,
                "product_name": row.get("product_name", ""),
                "quantity": int(row.get("stock_on_hand", row.get("quantity", 0)) or 0),
                "stock_on_hand": int(row.get("stock_on_hand", 0) or 0),
                "days_since_last_sale": row.get("days_since_last_sale"),
                "sales_velocity_30d": row.get("sales_velocity_30d"),
                "sales_velocity_90d": row.get("sales_velocity_90d"),
                "days_of_cover": row.get("days_of_cover"),
                "inventory_value": row.get("inventory_value"),
                "classification_reason": row.get("classification_reason", ""),
                "score": score,
                "severity": severity_from_score(score),
                "message": (
                    f"{cls.replace('_', ' ').title()} — {sku}: "
                    f"{row.get('classification_reason', '')}"
                ),
                "recommendation": _CLASSIFICATION_RECOMMENDATIONS.get(cls, ""),
            })
        return out[:cap]

    def _reorder_suggestions(self, risk_rows: list[dict]) -> list[dict]:
        suggestions = []
        for row in risk_rows:
            if row.get("classification") != CLASSIFICATION_LOW_STOCK:
                continue
            v30 = float(row.get("sales_velocity_30d", 0) or 0)
            qty = int(row.get("stock_on_hand", 0) or 0)
            cover = row.get("days_of_cover")
            if v30 <= 0 or cover is None:
                continue
            reorder_qty = int(v30 * 30 - qty)
            if reorder_qty <= 0:
                continue
            suggestions.append({
                "sku": row.get("sku"),
                "current_qty": qty,
                "suggested_reorder": reorder_qty,
                "days_of_cover": float(cover),
                "urgency": "high" if float(cover) < 7 else "medium",
            })
        return sorted(suggestions, key=lambda x: x["days_of_cover"])[:20]

    def _empty_result(self) -> dict:
        return {
            "inventory": pd.DataFrame(),
            "risk_rows": [],
            "alerts": [],
            "reorder_suggestions": [],
            "summary": {
                "avg_health_score": 0,
                "low_stock_count": 0,
                "overstock_count": 0,
                "slow_moving_count": 0,
                "dead_inventory_count": 0,
                "healthy_count": 0,
                "insufficient_activity_count": 0,
                "dead_inventory_value": 0,
                "recoverable_dead_inventory_value": 0,
                "slow_moving_value": 0,
                "overstock_value": 0,
                "healthy_inventory_value": 0,
            },
        }
