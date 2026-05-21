import pandas as pd
import numpy as np

from app.utils.scoring import clamp, weighted_score


class ProductIntelligenceEngine:
    """Deterministic product performance and trend analysis."""

    def analyze(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> dict:
        if products_df.empty:
            return self._empty_result()

        sales_agg = self._aggregate_sales(sales_df)
        merged = products_df.merge(sales_agg, on="sku", how="left", suffixes=("", "_sales"))
        merged["revenue"] = merged.get("revenue", pd.Series(0)).fillna(0)
        merged["units_sold"] = merged.get("units_sold", pd.Series(0)).fillna(0).astype(int)

        merged = self._compute_trends(merged, sales_df)
        merged["health_score"] = merged.apply(self._health_score, axis=1)
        merged["trend_indicator"] = merged.apply(self._trend_label, axis=1)
        merged = merged.sort_values("health_score", ascending=False)
        merged["performance_rank"] = range(1, len(merged) + 1)

        top_sellers = merged.nlargest(10, "revenue")[["sku", "title", "revenue", "units_sold", "health_score", "trend_indicator"]]
        worst = merged.nsmallest(10, "health_score")[["sku", "title", "revenue", "health_score", "trend_indicator"]]
        rising = merged[merged["trend_indicator"] == "rising"].head(10)
        declining = merged[merged["trend_indicator"] == "declining"].head(10)
        if "volatility" in merged.columns and merged["volatility"].notna().any():
            threshold = merged["volatility"].quantile(0.85)
            unstable = merged[merged["volatility"] > threshold].head(10)
        else:
            unstable = merged.iloc[0:0]

        return {
            "products": merged,
            "top_sellers": top_sellers.to_dict(orient="records"),
            "worst_performers": worst.to_dict(orient="records"),
            "fast_rising": rising.to_dict(orient="records") if not rising.empty else [],
            "declining": declining.to_dict(orient="records") if not declining.empty else [],
            "unstable": unstable.to_dict(orient="records") if not unstable.empty else [],
            "summary": {
                "avg_health_score": float(merged["health_score"].mean()),
                "rising_count": int((merged["trend_indicator"] == "rising").sum()),
                "declining_count": int((merged["trend_indicator"] == "declining").sum()),
            },
        }

    def _aggregate_sales(self, sales_df: pd.DataFrame) -> pd.DataFrame:
        if sales_df.empty:
            return pd.DataFrame(columns=["sku", "revenue", "units_sold"])
        agg = sales_df.groupby("sku").agg(
            revenue=("revenue", "sum"),
            units_sold=("quantity", "sum"),
        ).reset_index()
        return agg

    def _compute_trends(self, merged: pd.DataFrame, sales_df: pd.DataFrame) -> pd.DataFrame:
        merged["growth_rate"] = 0.0
        merged["volatility"] = 0.0
        if sales_df.empty:
            return merged
        if "aggregated" in sales_df.columns and sales_df["aggregated"].any():
            return merged
        if "sold_at" not in sales_df.columns:
            return merged

        sales_df = sales_df.copy()
        sales_df["sold_at"] = pd.to_datetime(sales_df["sold_at"], errors="coerce")
        sales_df = sales_df.dropna(subset=["sold_at"])
        if sales_df.empty:
            return merged

        mid = sales_df["sold_at"].median()
        recent = sales_df[sales_df["sold_at"] >= mid].groupby("sku")["revenue"].sum()
        prior = sales_df[sales_df["sold_at"] < mid].groupby("sku")["revenue"].sum()

        growth = ((recent - prior) / prior.replace(0, np.nan)).fillna(0)
        merged["growth_rate"] = merged["sku"].map(growth).fillna(0)

        daily = sales_df.groupby(["sku", sales_df["sold_at"].dt.date])["revenue"].sum().reset_index()
        vol = daily.groupby("sku")["revenue"].std().fillna(0)
        merged["volatility"] = merged["sku"].map(vol).fillna(0)
        return merged

    def _health_score(self, row) -> float:
        revenue_score = clamp(min(row.get("revenue", 0) / 1000, 1) * 100)
        margin = row.get("margin_pct") or row.get("margin_pct_sales") or 0
        margin_score = clamp(margin * 2) if margin else 50
        growth = row.get("growth_rate", 0)
        growth_score = clamp(50 + growth * 100)
        vol = row.get("volatility", 0)
        stability_score = clamp(100 - min(vol / 10, 100))
        return round(
            weighted_score([
                (revenue_score, 0.35),
                (margin_score, 0.25),
                (growth_score, 0.25),
                (stability_score, 0.15),
            ]),
            1,
        )

    def _trend_label(self, row) -> str:
        g = row.get("growth_rate", 0)
        if g > 0.15:
            return "rising"
        if g < -0.15:
            return "declining"
        if row.get("volatility", 0) > 50:
            return "unstable"
        return "stable"

    def _empty_result(self) -> dict:
        return {
            "products": pd.DataFrame(),
            "top_sellers": [],
            "worst_performers": [],
            "fast_rising": [],
            "declining": [],
            "unstable": [],
            "summary": {"avg_health_score": 0, "rising_count": 0, "declining_count": 0},
        }
