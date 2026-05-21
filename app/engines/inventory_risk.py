import pandas as pd

from app.config import get_settings
from app.utils.dataframe_ops import top_n_issues
from app.utils.scoring import clamp, severity_from_score


class InventoryRiskEngine:
    """Inventory health, dead stock, and reorder intelligence (vectorized)."""

    def analyze(self, inventory_df: pd.DataFrame, sales_df: pd.DataFrame, products_df: pd.DataFrame) -> dict:
        settings = get_settings()
        if inventory_df.empty:
            return self._empty_result()

        df = inventory_df.copy()
        sales_velocity = self._sales_velocity(sales_df)
        df["daily_velocity"] = df["sku"].astype(str).map(sales_velocity).fillna(0)

        qty = pd.to_numeric(df.get("quantity_on_hand", 0), errors="coerce").fillna(0)
        days = pd.to_numeric(df.get("days_in_stock", 0), errors="coerce").fillna(0)
        velocity = df["daily_velocity"].astype(float)

        stock_score = qty.apply(
            lambda q: 100 if q > settings.low_stock_threshold else clamp(q / max(settings.low_stock_threshold, 1) * 100)
        )
        velocity_score = velocity.apply(lambda v: clamp(min(v * 30, 100)))
        age_penalty = days.apply(lambda d: clamp(d / max(settings.dead_inventory_days, 1) * 100))
        age_score = 100 - age_penalty
        df["inventory_health_score"] = (
            stock_score * 0.4 + velocity_score * 0.35 + age_score * 0.25
        ).round(1)
        df["risk_level"] = df["inventory_health_score"].apply(
            lambda s: severity_from_score(100 - float(s))
        )

        alerts: list[dict] = []
        low_stock = df[qty <= settings.low_stock_threshold]
        alerts.extend(self._alerts_from_mask(low_stock, "low_stock", 85, "Restock immediately"))

        days_cover = qty / velocity.replace(0, pd.NA)
        stockout = df[(days_cover < 7) & (qty > 0) & (velocity > 0)]
        alerts.extend(self._alerts_from_mask(stockout, "stockout_risk", 88, "Reorder before stockout"))

        overstock = df[(days >= settings.overstock_days) & (velocity < 0.1)]
        alerts.extend(self._alerts_from_mask(overstock, "overstock", 60, "Reduce purchase orders"))

        dead = df[days >= settings.dead_inventory_days]
        alerts.extend(self._alerts_from_mask(dead, "dead_inventory", 90, "Consider liquidation"))

        reorder = self._reorder_suggestions_vectorized(df, settings)
        dead_value = self._dead_inventory_value(dead, products_df)

        return {
            "inventory": df,
            "alerts": top_n_issues(alerts, settings.analytics_issue_cap),
            "reorder_suggestions": reorder,
            "summary": {
                "avg_health_score": float(df["inventory_health_score"].mean()),
                "low_stock_count": int(len(low_stock)),
                "overstock_count": int(len(overstock)),
                "dead_inventory_count": int(len(dead)),
                "dead_inventory_value": round(dead_value, 2),
            },
        }

    def _alerts_from_mask(
        self, subset: pd.DataFrame, alert_type: str, score: float, recommendation: str
    ) -> list[dict]:
        if subset.empty:
            return []
        cap = get_settings().analytics_issue_cap
        records = subset.head(cap).to_dict("records")
        out = []
        for row in records:
            sku = row.get("sku", "")
            out.append({
                "type": alert_type,
                "sku": sku,
                "quantity": int(row.get("quantity_on_hand", 0) or 0),
                "score": score,
                "severity": severity_from_score(score),
                "message": f"{alert_type.replace('_', ' ').title()} — {sku}",
                "recommendation": recommendation,
            })
        return out

    def _dead_inventory_value(self, dead: pd.DataFrame, products_df: pd.DataFrame) -> float:
        if dead.empty or products_df.empty or "sku" not in products_df.columns:
            return 0.0
        prices = products_df.drop_duplicates("sku").set_index("sku")["price"]
        merged = dead.merge(prices.rename("price"), on="sku", how="left")
        merged["price"] = pd.to_numeric(merged["price"], errors="coerce").fillna(0)
        merged["quantity_on_hand"] = pd.to_numeric(merged["quantity_on_hand"], errors="coerce").fillna(0)
        return float((merged["price"] * merged["quantity_on_hand"]).sum())

    def _sales_velocity(self, sales_df: pd.DataFrame) -> dict[str, float]:
        if sales_df.empty or "sku" not in sales_df.columns:
            return {}
        work = sales_df.copy()
        if "aggregated" in work.columns and bool(work["aggregated"].any()):
            days = 30
        elif "sold_at" in work.columns:
            work["sold_at"] = pd.to_datetime(work["sold_at"], errors="coerce")
            span = (work["sold_at"].max() - work["sold_at"].min()).days
            days = max(int(span) if pd.notna(span) else 30, 1)
        else:
            days = 30
        qty = pd.to_numeric(work.get("quantity", 0), errors="coerce").fillna(0)
        work["_qty"] = qty
        vel = work.groupby("sku", as_index=True)["_qty"].sum() / days
        return vel.to_dict()

    def _reorder_suggestions_vectorized(self, df: pd.DataFrame, settings) -> list[dict]:
        qty = pd.to_numeric(df["quantity_on_hand"], errors="coerce").fillna(0)
        velocity = df["daily_velocity"].astype(float)
        mask = velocity > 0
        subset = df.loc[mask].copy()
        if subset.empty:
            return []
        subset["_qty"] = qty[mask]
        subset["_vel"] = velocity[mask]
        subset["_days_cover"] = subset["_qty"] / subset["_vel"]
        need = subset[subset["_days_cover"] < 14]
        if need.empty:
            return []
        suggestions = []
        for row in need.head(20).to_dict("records"):
            reorder_qty = int(row["_vel"] * 30 - row["_qty"])
            if reorder_qty <= 0:
                continue
            suggestions.append({
                "sku": row.get("sku"),
                "current_qty": int(row["_qty"]),
                "suggested_reorder": reorder_qty,
                "days_of_cover": round(float(row["_days_cover"]), 1),
                "urgency": "high" if row["_days_cover"] < 7 else "medium",
            })
        return sorted(suggestions, key=lambda x: x["days_of_cover"])

    def _empty_result(self) -> dict:
        return {
            "inventory": pd.DataFrame(),
            "alerts": [],
            "reorder_suggestions": [],
            "summary": {
                "avg_health_score": 0,
                "low_stock_count": 0,
                "overstock_count": 0,
                "dead_inventory_count": 0,
                "dead_inventory_value": 0,
            },
        }
