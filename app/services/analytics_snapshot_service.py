"""Unified analytics snapshot — single source of truth for KPIs, charts, and exports."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.schemas.analytics import DashboardMetrics
from app.services.active_dataset_service import ActiveDatasetService
from app.services.analysis_state import AnalysisStateService
from app.services.analytics_orchestrator import AnalyticsOrchestrator
from app.utils.analysis_selection import (
    analysis_cache_key,
    selection_fingerprint,
    unified_cache_key,
    unified_snapshot_type,
)
from app.services.dataframe_loader import DataframeLoader
from app.services.metrics_engine import MetricsEngine
from app.utils.app_timezone import as_local_iso, naive_local_now
from app.utils.cache import analytics_cache
from app.utils.json_safe import sanitize_for_json

logger = logging.getLogger("commerceflow.snapshot")

ROOT = Path(__file__).resolve().parents[2]
MARKETING_SNAPSHOT_PATH = ROOT / "data" / "demo_companies" / "atlas_analytics_snapshot.json"


def format_preview_metrics(metrics: dict[str, Any]) -> dict[str, str]:
    """Human-readable KPI strings (landing + executive summary)."""
    rev = float(metrics.get("total_revenue") or 0)
    dead = float(metrics.get("dead_inventory_value") or 0)
    orders = int(metrics.get("total_orders") or 0)
    products = int(metrics.get("product_count") or 0)
    alerts = int(metrics.get("active_alerts") or 0)
    margin = metrics.get("gross_margin_pct")
    inv_eff = metrics.get("inventory_efficiency")
    risk = metrics.get("operational_risk_score")

    def money(v: float) -> str:
        if v >= 1_000_000:
            return f"${v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"${v / 1_000:.0f}K"
        return f"${v:,.0f}"

    return {
        "revenue": money(rev),
        "grossMargin": f"{float(margin):.1f}%" if margin is not None else "—",
        "inventoryEfficiency": f"{float(inv_eff):.1f}%" if inv_eff is not None else "—",
        "riskScore": f"{float(risk):.1f}" if risk is not None else "—",
        "deadInventory": money(dead),
        "ordersAnalyzed": f"{orders:,}",
        "activeProducts": f"{products:,}",
        "operationalAlerts": f"{alerts:,}",
    }


def chart_preview_bars(revenue_trend: list[dict], *, points: int = 12) -> list[int]:
    if not revenue_trend:
        return []
    values = [float(r.get("revenue") or 0) for r in revenue_trend[-points:]]
    if not values or max(values) <= 0:
        return []
    peak = max(values)
    return [max(8, min(100, int(round(100 * v / peak)))) for v in values]


def chart_category_mix(category_breakdown: list[dict], *, limit: int = 7) -> list[dict]:
    rows = sorted(category_breakdown, key=lambda r: float(r.get("revenue") or 0), reverse=True)
    total = sum(float(r.get("revenue") or 0) for r in rows)
    if total <= 0:
        return []
    top = rows[:limit]
    rest = rows[limit:]
    out = [
        {"label": str(r.get("category") or "Other"), "pct": int(round(100 * float(r["revenue"]) / total))}
        for r in top
        if float(r.get("revenue") or 0) > 0
    ]
    if rest:
        other = sum(float(r.get("revenue") or 0) for r in rest)
        if other > 0:
            out.append({"label": "Other", "pct": max(0, 100 - sum(x["pct"] for x in out))})
    return out


def chart_inventory_risk_mix(inventory_risk: dict[str, int]) -> list[dict]:
    total = sum(int(v) for v in inventory_risk.values())
    if total <= 0:
        return []
    order = ("Low", "Medium", "Critical")
    return [
        {"label": label, "pct": int(round(100 * int(inventory_risk.get(label, 0)) / total))}
        for label in order
        if int(inventory_risk.get(label, 0)) > 0
    ]


class AnalyticsSnapshotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.loader = DataframeLoader(session)
        self.orchestrator = AnalyticsOrchestrator(session)

    async def build_chart_data(
        self,
        selection: dict[str, int | None],
        analysis: dict,
        *,
        products_df=None,
        inventory_df=None,
        sales_df=None,
    ) -> dict[str, Any]:
        from app.utils.chart_data_builder import (
            build_category_breakdown,
            build_inventory_risk_breakdown,
            build_revenue_trend,
            ensure_chart_payload,
            fallback_revenue_trend,
        )

        settings = get_settings()
        revenue_trend: list[dict] = []
        sid = selection.get("sales_import_id")
        pid = selection.get("products_import_id")
        if sid:
            daily = await self.loader.load_sales_daily_revenue(sid, limit_days=90)
            revenue_trend = build_revenue_trend(daily)
        if not revenue_trend and sales_df is not None and len(sales_df) <= settings.sales_aggregate_above_rows:
            revenue_trend = fallback_revenue_trend(sales_df)

        category_breakdown: list[dict] = []
        if sid and pid:
            cat_df = await self.loader.load_sales_category_revenue(sid, pid)
            if not cat_df.empty:
                from app.utils.chart_data_builder import top_category_breakdown

                category_breakdown = top_category_breakdown(cat_df.to_dict(orient="records"))
        if not category_breakdown and products_df is not None and sales_df is not None:
            category_breakdown = await build_category_breakdown(
                self.session, selection, products_df, sales_df
            )

        inventory_risk = build_inventory_risk_breakdown(inventory_df, analysis)
        return ensure_chart_payload(
            {
                "revenue_trend": revenue_trend,
                "category_breakdown": category_breakdown,
                "inventory_risk": inventory_risk,
            }
        )

    async def build_unified(
        self,
        selection: dict[str, int | None],
        *,
        analysis: dict | None = None,
    ) -> dict[str, Any]:
        bundle = await self.loader.load(selection)
        if analysis is None:
            pipeline = await self.orchestrator.run_analysis_pipeline(
                use_cache=True, selection=selection
            )
            analysis = pipeline.get("result") or {}

        metrics, traces = MetricsEngine.compute(
            bundle.products, bundle.sales, bundle.inventory, analysis, selection
        )
        charts = await self.build_chart_data(
            selection,
            analysis,
            products_df=bundle.products,
            inventory_df=bundle.inventory,
            sales_df=bundle.sales,
        )
        metrics_dict = metrics.model_dump()
        generated = as_local_iso(naive_local_now()) or ""
        fingerprint = selection_fingerprint(selection)

        preview = format_preview_metrics(metrics_dict)
        preview["revenueTrendBars"] = chart_preview_bars(charts.get("revenue_trend") or [])
        preview["categoryMix"] = chart_category_mix(charts.get("category_breakdown") or [])
        preview["inventoryRisk"] = chart_inventory_risk_mix(charts.get("inventory_risk") or {})

        return sanitize_for_json({
            "selection": selection,
            "analysis_id": fingerprint,
            "generated_at": generated,
            "metrics": metrics_dict,
            "metric_traces": traces,
            "charts": charts,
            "analysis": analysis,
            "preview": preview,
        })

    async def persist_unified(self, selection: dict[str, int | None], unified: dict[str, Any]) -> None:
        payload = sanitize_for_json(unified)
        snap_type = unified_snapshot_type(selection)
        self.session.add(
            AnalyticsSnapshot(
                snapshot_type=snap_type,
                payload_json=json.dumps(payload, default=str),
            )
        )
        await self.session.flush()
        analytics_cache.set(unified_cache_key(selection), payload)
        analytics_cache.set(analysis_cache_key(selection), payload.get("analysis") or {})
        analytics_cache.set("full_analysis", payload.get("analysis") or {})

    async def load_from_db(self, selection: dict[str, int | None]) -> dict[str, Any] | None:
        snap_type = unified_snapshot_type(selection)
        result = await self.session.execute(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.snapshot_type == snap_type)
            .order_by(AnalyticsSnapshot.created_at.desc(), AnalyticsSnapshot.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if not row or not row.payload_json:
            return None
        try:
            return json.loads(row.payload_json)
        except json.JSONDecodeError:
            logger.warning("Invalid unified snapshot JSON for %s", snap_type)
            return None

    async def get_current(self, *, rebuild_if_missing: bool = False) -> dict[str, Any] | None:
        if not await AnalysisStateService(self.session).has_generated_analysis():
            return None

        active = await ActiveDatasetService(self.session).get_active()
        if not active.has_selection:
            return None

        selection = {
            "products_import_id": active.products_import_id,
            "sales_import_id": active.sales_import_id,
            "inventory_import_id": active.inventory_import_id,
        }

        cached = analytics_cache.get(unified_cache_key(selection))
        if cached:
            return cached

        stored = await self.load_from_db(selection)
        if stored:
            analytics_cache.set(unified_cache_key(selection), stored)
            return stored

        if not rebuild_if_missing:
            return None

        unified = await self.build_unified(selection)
        await self.persist_unified(selection, unified)
        return unified

    async def current_analysis_id(self) -> str | None:
        unified = await self.get_current(rebuild_if_missing=False)
        if unified:
            return unified.get("analysis_id")
        active = await ActiveDatasetService(self.session).get_active()
        if not active.has_selection:
            return None
        return selection_fingerprint(
            {
                "products_import_id": active.products_import_id,
                "sales_import_id": active.sales_import_id,
                "inventory_import_id": active.inventory_import_id,
            }
        )

    @staticmethod
    def marketing_preview() -> dict[str, Any]:
        """Static Atlas marketing preview (build-time snapshot file)."""
        if not MARKETING_SNAPSHOT_PATH.is_file():
            return {}
        try:
            data = json.loads(MARKETING_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Marketing snapshot unavailable: %s", exc)
            return {}
        preview = data.get("preview") or {}
        return sanitize_for_json({
            "source": "atlas_marketing_snapshot",
            "generated_at": data.get("generated_at"),
            "preview": preview,
            "metrics": data.get("metrics") or {},
            "charts": {
                "revenue_trend_bars": preview.get("revenueTrendBars") or [],
                "category_mix": preview.get("categoryMix") or [],
                "inventory_risk": preview.get("inventoryRisk") or [],
            },
        })
