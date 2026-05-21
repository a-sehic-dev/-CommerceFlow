import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.analytics import DashboardMetrics
from app.services.active_dataset_service import ActiveDatasetService
from app.services.analysis_state import AnalysisStateService
from app.services.analytics_orchestrator import AnalyticsOrchestrator
from app.services.dataframe_loader import DataframeLoader
from app.services.metrics_engine import MetricsEngine
from app.utils.analysis_logger import log_exception, log_stage


class BusinessInsightsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.orchestrator = AnalyticsOrchestrator(session)
        self.loader = DataframeLoader(session)

    async def get_executive_dashboard(self) -> dict:
        active = await ActiveDatasetService(self.session).get_active()
        if not active.has_selection:
            return {
                "metrics": DashboardMetrics().model_dump(),
                "metric_traces": {},
                "charts": {"revenue_trend": [], "category_breakdown": [], "margin_trend": []},
                "analysis_summary": {},
                "top_sellers": [],
                "recommendations": [],
                "active_datasets": active.model_dump(),
                "requires_dataset_selection": True,
                "requires_analysis_generation": False,
                "has_generated_analysis": False,
                "partial": False,
                "warnings": [],
            }

        if not await AnalysisStateService(self.session).has_generated_analysis():
            return self._pending_analysis_dashboard(active)

        selection = {
            "products_import_id": active.products_import_id,
            "sales_import_id": active.sales_import_id,
            "inventory_import_id": active.inventory_import_id,
        }

        warnings: list[str] = []
        analysis: dict = {
            "profit_leakage": {"issue_count": 0, "recommendations": [], "issues": []},
            "inventory_risk": {"alerts": [], "summary": {}},
            "data_cleaning": {"quality_score": None, "issues": []},
            "product_intelligence": {"summary": {}, "top_sellers": []},
        }
        pipeline: dict = {"success": False, "failed_modules": [], "errors": []}

        try:
            bundle = await self.loader.load(selection)
        except Exception as exc:
            log_exception("dashboard_load", exc)
            return self._error_dashboard(active, f"Failed to load datasets: {exc}")

        try:
            pipeline = await self.orchestrator.run_analysis_pipeline(
                use_cache=True, selection=selection
            )
            if pipeline.get("result"):
                analysis = {**analysis, **pipeline["result"]}
            if pipeline.get("failed_modules"):
                warnings.append(
                    f"Partial analytics — modules with warnings: {', '.join(pipeline['failed_modules'])}"
                )
        except Exception as exc:
            log_exception("dashboard_analysis", exc)
            warnings.append(f"Analysis modules unavailable: {exc}")

        try:
            metrics, traces = MetricsEngine.compute(
                bundle.products, bundle.sales, bundle.inventory, analysis, selection
            )
        except Exception as exc:
            log_exception("dashboard_metrics", exc)
            metrics, traces = DashboardMetrics(), {}
            warnings.append(f"Some KPIs unavailable: {exc}")

        try:
            charts = await self._chart_data(selection, bundle)
        except Exception as exc:
            log_exception("dashboard_charts", exc)
            charts = {"revenue_trend": [], "category_breakdown": [], "margin_trend": []}
            warnings.append("Charts could not be built from sales data")

        return {
            "metrics": metrics.model_dump(),
            "metric_traces": traces,
            "charts": charts,
            "active_datasets": active.model_dump(),
            "requires_dataset_selection": False,
            "requires_analysis_generation": False,
            "has_generated_analysis": True,
            "partial": bool(warnings),
            "warnings": warnings,
            "dataset_info": bundle.info,
            "analysis_summary": {
                "profit_issues": analysis.get("profit_leakage", {}).get("issue_count", 0),
                "leakage_pct_of_revenue": analysis.get("profit_leakage", {}).get("leakage_pct_of_revenue"),
                "inventory_alerts": len(analysis.get("inventory_risk", {}).get("alerts", [])),
                "data_quality": analysis.get("data_cleaning", {}).get("quality_score"),
                "avg_product_health": analysis.get("product_intelligence", {})
                .get("summary", {})
                .get("avg_health_score"),
            },
            "top_sellers": analysis.get("product_intelligence", {}).get("top_sellers", [])[:5],
            "recommendations": analysis.get("profit_leakage", {}).get("recommendations", [])[:5],
            "failed_modules": pipeline.get("failed_modules", []),
        }

    def _pending_analysis_dashboard(self, active) -> dict:
        return {
            "metrics": DashboardMetrics().model_dump(),
            "metric_traces": {},
            "charts": {"revenue_trend": [], "category_breakdown": [], "margin_trend": []},
            "analysis_summary": {},
            "top_sellers": [],
            "recommendations": [],
            "active_datasets": active.model_dump(),
            "requires_dataset_selection": False,
            "requires_analysis_generation": True,
            "has_generated_analysis": False,
            "partial": False,
            "warnings": [],
        }

    def _error_dashboard(self, active, message: str) -> dict:
        return {
            "metrics": DashboardMetrics().model_dump(),
            "metric_traces": {},
            "charts": {"revenue_trend": [], "category_breakdown": [], "margin_trend": []},
            "analysis_summary": {},
            "top_sellers": [],
            "recommendations": [],
            "active_datasets": active.model_dump(),
            "requires_dataset_selection": False,
            "requires_analysis_generation": False,
            "has_generated_analysis": False,
            "partial": True,
            "warnings": [message],
        }

    async def _chart_data(self, selection: dict, bundle) -> dict:
        sid = selection.get("sales_import_id")
        pid = selection.get("products_import_id")
        if not sid:
            return {"revenue_trend": [], "category_breakdown": [], "margin_trend": []}

        daily = await self.loader.load_sales_daily_revenue(sid)
        revenue_trend = daily.to_dict(orient="records") if not daily.empty else []

        category_breakdown: list[dict] = []
        if pid and not bundle.sales.empty and "sku" in bundle.sales.columns:
            products = await self.session.execute(
                select(Product.sku, Product.category).where(Product.import_id == pid)
            )
            prod_df = pd.DataFrame(
                [{"sku": r.sku, "category": r.category or "Uncategorized"} for r in products.all()]
            )
            sales = bundle.sales[["sku", "revenue"]].copy()
            sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce").fillna(0)
            merged = sales.merge(prod_df, on="sku", how="left")
            merged["category"] = merged["category"].fillna("Uncategorized")
            cat = merged.groupby("category", as_index=False)["revenue"].sum()
            category_breakdown = cat.to_dict(orient="records")

        return {
            "revenue_trend": revenue_trend,
            "category_breakdown": category_breakdown,
            "margin_trend": [],
        }
