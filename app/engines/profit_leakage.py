import pandas as pd

from app.config import get_settings
from app.engines.data_cleaning import DataCleaningEngine
from app.utils.dataframe_ops import top_n_issues
from app.utils.scoring import clamp, severity_from_score


class ProfitLeakageEngine:
    """Weighted, revenue-bounded profit leakage detection."""

    TARGET_MARGIN_PCT = 25.0
    DEAD_INVENTORY_RECOVERY_RATE = 0.25
    CATEGORY_RECOVERY_RATE = 0.15
    DATA_QUALITY_RATE = 0.001
    DUPLICATE_RATE = 0.0005
    HOLDING_COST_ANNUAL_RATE = 0.18
    MAX_LEAKAGE_PCT_OF_REVENUE = 0.15

    def analyze(
        self,
        products_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        inventory_df: pd.DataFrame | None = None,
        data_quality_issues: list[dict] | None = None,
    ) -> dict:
        settings = get_settings()
        total_revenue = self._total_revenue(sales_df)
        sku_revenue = self._sku_revenue(sales_df)
        issues: list[dict] = []

        if not products_df.empty:
            issues.extend(
                self._low_margin_products(
                    products_df, sku_revenue, settings.margin_warning_pct
                )
            )
            issues.extend(self._pricing_inconsistencies(products_df))
            issues.extend(self._negative_profit_products(products_df, sku_revenue))

        if not sales_df.empty:
            issues.extend(self._suspicious_discounts(sales_df))
            if not self._is_aggregated_sales(sales_df):
                issues.extend(self._revenue_anomalies(sales_df, total_revenue))

        if inventory_df is not None and not inventory_df.empty:
            issues.extend(
                self._dead_inventory_impact(products_df, inventory_df, settings)
            )
            issues.extend(
                self._overstock_holding_cost(products_df, inventory_df, sales_df, settings)
            )
            issues.extend(self._missing_inventory(products_df, inventory_df, sku_revenue))

        if not products_df.empty and "category" in products_df.columns and not sales_df.empty:
            issues.extend(
                self._underperforming_categories(products_df, sales_df, total_revenue)
            )

        quality_issues = data_quality_issues
        if quality_issues is None and not products_df.empty:
            quality_issues = DataCleaningEngine().analyze(products_df).get("issues", [])
        if quality_issues and total_revenue > 0:
            issues.extend(self._data_quality_impact(quality_issues, total_revenue))

        for issue in issues:
            issue["severity"] = severity_from_score(issue.get("score", 50))

        settings = get_settings()
        issues = top_n_issues(issues, settings.analytics_issue_cap)
        raw_total = sum(float(i.get("estimated_impact", 0) or 0) for i in issues)
        total_leakage, cap_note = self._cap_leakage(raw_total, total_revenue)

        if raw_total > 0 and total_leakage < raw_total:
            scale = total_leakage / raw_total
            for issue in issues:
                issue["estimated_impact"] = round(
                    float(issue.get("estimated_impact", 0) or 0) * scale, 2
                )

        leakage_pct = (total_leakage / total_revenue * 100) if total_revenue > 0 else 0

        return {
            "issues": issues,
            "total_estimated_leakage": round(total_leakage, 2),
            "raw_estimated_leakage": round(raw_total, 2),
            "leakage_pct_of_revenue": round(leakage_pct, 2),
            "total_revenue_basis": round(total_revenue, 2),
            "issue_count": len(issues),
            "critical_count": sum(1 for i in issues if i.get("severity") == "critical"),
            "recommendations": self._recommendations(issues),
            "metric_traces": {
                "total_formula": "MIN(SUM(weighted impacts), revenue * 0.15, revenue)",
                "cap_note": cap_note,
                "dead_inventory": f"inventory_value * {self.DEAD_INVENTORY_RECOVERY_RATE}",
                "low_margin": f"sku_revenue * (target_margin - actual_margin), target={self.TARGET_MARGIN_PCT}%",
                "overstock": f"holding_value * ({self.HOLDING_COST_ANNUAL_RATE} / 365) * excess_days",
                "data_quality": f"total_revenue * {self.DATA_QUALITY_RATE} per issue (capped)",
            },
        }

    def _is_aggregated_sales(self, sales_df: pd.DataFrame) -> bool:
        return "aggregated" in sales_df.columns and bool(sales_df["aggregated"].any())

    def _total_revenue(self, sales_df: pd.DataFrame) -> float:
        if sales_df.empty or "revenue" not in sales_df.columns:
            return 0.0
        return float(sales_df["revenue"].sum())

    def _sku_revenue(self, sales_df: pd.DataFrame) -> dict[str, float]:
        if sales_df.empty or "revenue" not in sales_df.columns:
            return {}
        return sales_df.groupby("sku")["revenue"].sum().to_dict()

    def _cap_leakage(self, raw_total: float, total_revenue: float) -> tuple[float, str]:
        if raw_total <= 0:
            return 0.0, "No leakage issues detected"
        if total_revenue <= 0:
            return round(raw_total, 2), "Capped using issue weights only (no sales revenue in selection)"
        max_allowed = total_revenue * self.MAX_LEAKAGE_PCT_OF_REVENUE
        capped = min(raw_total, max_allowed, total_revenue)
        note = (
            f"Scaled from ${raw_total:,.0f} to ${capped:,.0f} "
            f"(max {self.MAX_LEAKAGE_PCT_OF_REVENUE:.0%} of revenue ${total_revenue:,.0f})"
            if capped < raw_total
            else f"Within revenue bounds (${capped:,.0f} of ${total_revenue:,.0f})"
        )
        return round(capped, 2), note

    def _low_margin_products(
        self, df: pd.DataFrame, sku_revenue: dict[str, float], threshold: float
    ) -> list[dict]:
        results = []
        work = df.copy()
        if "margin_pct" not in work.columns:
            if "cost" in work.columns and "price" in work.columns:
                work["margin_pct"] = (
                    (work["price"] - work["cost"]) / work["price"].replace(0, pd.NA)
                ) * 100
            else:
                return results

        low = work[work["margin_pct"].fillna(0) < threshold]
        for _, row in low.iterrows():
            sku = str(row.get("sku", ""))
            actual = float(row.get("margin_pct", 0) or 0)
            revenue = float(sku_revenue.get(sku, 0))
            if revenue <= 0:
                revenue = float(row.get("price", 0) or 0)
            delta = max(0, (self.TARGET_MARGIN_PCT - actual) / 100)
            impact = revenue * delta
            if impact <= 0:
                continue
            results.append({
                "type": "low_margin",
                "sku": sku,
                "title": row.get("title", ""),
                "score": clamp(100 - actual * 2),
                "estimated_impact": round(impact, 2),
                "message": f"Margin {actual:.1f}% below {threshold}% — recoverable delta {delta*100:.1f}%",
                "recommendation": "Review pricing or supplier costs",
            })
        return results

    def _negative_profit_products(
        self, df: pd.DataFrame, sku_revenue: dict[str, float]
    ) -> list[dict]:
        results = []
        if "cost" not in df.columns or "price" not in df.columns:
            return results
        negative = df[df["cost"] > df["price"]]
        for _, row in negative.iterrows():
            sku = str(row.get("sku", ""))
            loss_per_unit = float(row["cost"] - row["price"])
            units_proxy = max(1, float(sku_revenue.get(sku, 0)) / max(float(row["price"] or 1), 1))
            impact = loss_per_unit * units_proxy
            results.append({
                "type": "negative_profit",
                "sku": sku,
                "title": row.get("title", ""),
                "score": 92,
                "estimated_impact": round(impact, 2),
                "message": f"Cost exceeds price by ${loss_per_unit:.2f} per unit",
                "recommendation": "Increase price or renegotiate supplier cost",
            })
        return results

    def _pricing_inconsistencies(self, df: pd.DataFrame) -> list[dict]:
        results = []
        if "compare_at_price" not in df.columns or "price" not in df.columns:
            return results
        inconsistent = df[
            (df["compare_at_price"].notna())
            & (df["compare_at_price"] > 0)
            & (df["price"] >= df["compare_at_price"])
        ]
        for _, row in inconsistent.iterrows():
            results.append({
                "type": "suspicious_pricing",
                "sku": row.get("sku", ""),
                "title": row.get("title", ""),
                "score": 65,
                "estimated_impact": 0,
                "message": "Sale price equals or exceeds compare-at price",
                "recommendation": "Fix compare-at pricing display",
            })
        return results

    def _suspicious_discounts(self, sales_df: pd.DataFrame) -> list[dict]:
        results = []
        if "discount_amount" not in sales_df.columns:
            return results
        valid = sales_df[sales_df["revenue"] > 0]
        high_discount = valid[valid["discount_amount"] > valid["revenue"] * 0.4]
        grouped = high_discount.groupby("sku").agg(
            total_discount=("discount_amount", "sum"),
            revenue=("revenue", "sum"),
        )
        for sku, row in grouped.iterrows():
            impact = min(float(row["total_discount"]), float(row["revenue"]) * 0.25)
            results.append({
                "type": "suspicious_discount",
                "sku": sku,
                "score": 70,
                "estimated_impact": round(impact, 2),
                "message": f"Heavy discounting detected (${row['total_discount']:,.0f})",
                "recommendation": "Audit discount rules and promotion strategy",
            })
        return results

    def _revenue_anomalies(self, sales_df: pd.DataFrame, total_revenue: float) -> list[dict]:
        results = []
        if "sold_at" not in sales_df.columns or total_revenue <= 0:
            return results
        daily = sales_df.copy()
        daily["sold_at"] = pd.to_datetime(daily["sold_at"], errors="coerce")
        rev = daily.groupby(daily["sold_at"].dt.date)["revenue"].sum()
        if len(rev) < 7:
            return results
        mean, std = rev.mean(), rev.std()
        if std == 0:
            return results
        anomalies = rev[rev < mean - 2 * std]
        for date, amount in anomalies.items():
            drop = max(0, float(mean - amount))
            impact = min(drop, total_revenue * 0.02)
            drop_pct = drop / mean * 100 if mean else 0
            results.append({
                "type": "revenue_drop",
                "sku": None,
                "score": clamp(drop_pct),
                "estimated_impact": round(impact, 2),
                "message": f"Abnormal revenue drop on {date} ({drop_pct:.0f}% below average)",
                "recommendation": "Investigate traffic, ads, and checkout issues",
            })
        return results

    def _dead_inventory_impact(
        self, products_df: pd.DataFrame, inventory_df: pd.DataFrame, settings
    ) -> list[dict]:
        results = []
        stale = inventory_df[inventory_df.get("days_in_stock", 0) >= settings.dead_inventory_days]
        if stale.empty:
            return results
        price_map = (
            products_df.set_index("sku")["price"].to_dict() if not products_df.empty else {}
        )
        title_map = (
            products_df.set_index("sku")["title"].to_dict() if not products_df.empty else {}
        )
        for _, row in stale.iterrows():
            sku = row.get("sku", "")
            value = float(price_map.get(sku, 0) or 0) * int(row.get("quantity_on_hand", 0) or 0)
            impact = value * self.DEAD_INVENTORY_RECOVERY_RATE
            if impact <= 0:
                continue
            results.append({
                "type": "dead_inventory",
                "sku": sku,
                "title": title_map.get(sku, ""),
                "score": 90,
                "estimated_impact": round(impact, 2),
                "message": f"Dead inventory {row.get('days_in_stock', 0)}+ days (${value:,.0f} at risk, 25% recoverable)",
                "recommendation": "Liquidate, bundle, or discount strategically",
            })
        return results

    def _overstock_holding_cost(
        self,
        products_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        settings,
    ) -> list[dict]:
        results = []
        velocity = {}
        if not sales_df.empty:
            sales_df = sales_df.copy()
            if "sold_at" in sales_df.columns:
                sales_df["sold_at"] = pd.to_datetime(sales_df["sold_at"], errors="coerce")
                days = max((sales_df["sold_at"].max() - sales_df["sold_at"].min()).days, 1)
            else:
                days = 30
            velocity = (sales_df.groupby("sku")["quantity"].sum() / days).to_dict()

        price_map = products_df.set_index("sku")["price"].to_dict() if not products_df.empty else {}
        overstock = inventory_df[
            (inventory_df.get("days_in_stock", 0).fillna(0) >= settings.overstock_days)
        ]
        for _, row in overstock.iterrows():
            sku = row.get("sku", "")
            daily_vel = float(velocity.get(sku, 0))
            if daily_vel >= 0.1:
                continue
            qty = int(row.get("quantity_on_hand", 0) or 0)
            unit_price = float(price_map.get(sku, 0) or 0)
            holding_value = unit_price * qty
            excess_days = max(int(row.get("days_in_stock", 0) or 0) - settings.overstock_days, 0)
            daily_rate = self.HOLDING_COST_ANNUAL_RATE / 365
            impact = holding_value * daily_rate * excess_days
            if impact <= 0:
                continue
            results.append({
                "type": "overstock",
                "sku": sku,
                "score": 60,
                "estimated_impact": round(impact, 2),
                "message": f"Overstock holding cost estimate ({excess_days} excess days)",
                "recommendation": "Reduce purchase orders and run clearance",
            })
        return results

    def _missing_inventory(
        self, products_df: pd.DataFrame, inventory_df: pd.DataFrame, sku_revenue: dict
    ) -> list[dict]:
        if products_df.empty or "sku" not in products_df.columns:
            return []
        inv_skus = set(inventory_df["sku"].astype(str)) if "sku" in inventory_df.columns else set()
        prod_skus = products_df["sku"].astype(str)
        missing = prod_skus[~prod_skus.isin(inv_skus)].drop_duplicates().head(100)
        results = []
        titles = products_df.set_index("sku")["title"].to_dict() if "title" in products_df.columns else {}
        for sku in missing:
            revenue = float(sku_revenue.get(sku, 0))
            if revenue <= 0:
                continue
            results.append({
                "type": "missing_inventory",
                "sku": sku,
                "title": titles.get(sku, ""),
                "score": 72,
                "estimated_impact": round(revenue * 0.01, 2),
                "message": "Product has sales but no inventory record",
                "recommendation": "Sync inventory records for this SKU",
            })
        return results[:25]

    def _underperforming_categories(
        self, products_df: pd.DataFrame, sales_df: pd.DataFrame, total_revenue: float
    ) -> list[dict]:
        results = []
        cat_map = products_df.set_index("sku")["category"].to_dict()
        sales = sales_df.copy()
        sales["category"] = sales["sku"].map(cat_map)
        cat_rev = sales.groupby("category")["revenue"].sum()
        if cat_rev.empty or total_revenue <= 0:
            return results
        threshold = cat_rev.quantile(0.25)
        top_rev = float(cat_rev.max())
        for cat, rev in cat_rev[cat_rev <= threshold].items():
            if pd.isna(cat):
                continue
            gap = max(0, top_rev - float(rev))
            impact = gap * self.CATEGORY_RECOVERY_RATE
            results.append({
                "type": "underperforming_category",
                "sku": None,
                "score": 55,
                "estimated_impact": round(impact, 2),
                "message": f"Category '{cat}' underperforming (${rev:,.0f} revenue)",
                "recommendation": "Refresh assortment or marketing for this category",
            })
        return results

    def _data_quality_impact(self, issues: list[dict], total_revenue: float) -> list[dict]:
        results = []
        per_issue_cap = total_revenue * self.DATA_QUALITY_RATE
        for issue in issues:
            issue_type = issue.get("type", "data_quality")
            if issue_type in ("missing_field", "invalid_price", "inconsistent_category"):
                weight = 0.5
            elif issue_type in ("duplicate_sku", "fuzzy_duplicate_title"):
                weight = self.DUPLICATE_RATE / self.DATA_QUALITY_RATE
            else:
                weight = 0.3
            impact = per_issue_cap * weight
            results.append({
                "type": issue_type,
                "sku": issue.get("sku"),
                "title": issue.get("field") or issue.get("type", ""),
                "score": issue.get("score", 50),
                "estimated_impact": round(impact, 2),
                "message": issue.get("message", "Data quality issue"),
                "recommendation": issue.get("recommendation", "Resolve data quality issue"),
            })
        return results

    def _recommendations(self, issues: list[dict]) -> list[str]:
        recs = list({i["recommendation"] for i in issues if i.get("recommendation")})[:8]
        if not recs:
            recs = ["No significant profit leakage detected. Maintain current pricing discipline."]
        return recs
