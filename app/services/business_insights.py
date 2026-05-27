import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import DashboardMetrics
from app.services.active_dataset_service import ActiveDatasetService
from app.services.analysis_state import AnalysisStateService
from app.services.analytics_snapshot_service import AnalyticsSnapshotService
from app.utils.analysis_logger import log_exception


class BusinessInsightsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.snapshots = AnalyticsSnapshotService(session)

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

        try:
            unified = await self.snapshots.get_current(rebuild_if_missing=False)
        except Exception as exc:
            log_exception("dashboard_snapshot", exc)
            return self._error_dashboard(active, f"Failed to load analytics snapshot: {exc}")

        if not unified:
            return self._pending_analysis_dashboard(active)

        analysis = unified.get("analysis") or {}
        warnings: list[str] = []
        return {
            "metrics": unified.get("metrics") or DashboardMetrics().model_dump(),
            "metric_traces": unified.get("metric_traces") or {},
            "charts": unified.get("charts")
            or {"revenue_trend": [], "category_breakdown": [], "margin_trend": []},
            "active_datasets": active.model_dump(),
            "requires_dataset_selection": False,
            "requires_analysis_generation": False,
            "has_generated_analysis": True,
            "partial": bool(warnings),
            "warnings": warnings,
            "analysis_id": unified.get("analysis_id"),
            "snapshot_generated_at": unified.get("generated_at"),
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
            "failed_modules": [],
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
