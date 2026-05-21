import csv
import json
from app.utils.app_timezone import filename_timestamp, naive_local_now
from io import BytesIO
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.alert import Alert
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sales import SalesRecord
from app.services.active_dataset_service import ActiveDatasetService
from app.services.analytics_orchestrator import AnalyticsOrchestrator
from app.services.metrics_engine import MetricsEngine
from app.utils.excel_workbook import (
    ENGINE_VERSION,
    build_enterprise_workbook,
    enterprise_filename,
    write_dataframe_sheet,
)
from openpyxl import Workbook


class ExportService:
    ENTERPRISE_SHEETS = (
        "Executive Summary",
        "Products Intelligence",
        "Inventory Health",
        "Alerts Center",
        "Profit Leakage",
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_export_meta(self) -> dict:
        selection = await self._active_selection()
        has_selection = any(selection.values())
        counts = await self._row_counts(selection)
        alerts_n = counts.get("alerts", 0)
        total_rows = counts.get("products", 0) + counts.get("sales", 0) + counts.get("inventory", 0)

        from app.services.analysis_state import AnalysisStateService
        from app.services.export_job_service import export_jobs

        has_analysis = await AnalysisStateService(self.session).has_generated_analysis()
        last = export_jobs.last_completed() if has_analysis else None
        estimates = {
            "enterprise": self._estimate_bytes(counts, "xlsx", enterprise=True),
            "summary": self._estimate_bytes(counts, "xlsx"),
            "products": self._estimate_bytes({"products": counts["products"]}, "csv"),
            "sales": self._estimate_bytes({"sales": counts["sales"]}, "csv"),
            "inventory": self._estimate_bytes({"inventory": counts["inventory"]}, "csv"),
            "alerts": self._estimate_bytes({"alerts": alerts_n}, "csv"),
            "profit_leakage": self._estimate_bytes(counts, "xlsx", small=True),
        }

        return {
            "has_selection": has_selection,
            "has_generated_analysis": has_analysis,
            "selection": selection,
            "row_counts": counts,
            "total_rows": total_rows,
            "enterprise_sheets": len(self.ENTERPRISE_SHEETS),
            "sheet_names": list(self.ENTERPRISE_SHEETS),
            "estimated_sizes": estimates,
            "last_export": last.to_dict() if last else None,
            "async_recommended": counts.get("sales", 0) > self.settings.sales_aggregate_above_rows
                or total_rows > 100_000,
        }

    def _estimate_bytes(self, counts: dict, fmt: str, *, enterprise: bool = False, small: bool = False) -> dict:
        rows = sum(counts.get(k, 0) for k in ("products", "sales", "inventory", "alerts"))
        if enterprise:
            rows = min(rows, self.settings.export_max_rows_per_sheet * 5)
            per_row = 180
        elif small:
            rows = min(rows, 500)
            per_row = 120
        else:
            per_row = 90 if fmt == "csv" else 150
        raw = max(rows, 1) * per_row
        if fmt == "xlsx":
            raw = int(raw * 1.4)
        return {"bytes": raw, "human": self._human_size(raw), "format": fmt}

    @staticmethod
    def _human_size(n: int) -> str:
        if n < 1024:
            return f"~{n} B"
        if n < 1024 * 1024:
            return f"~{n / 1024:.0f} KB"
        return f"~{n / (1024 * 1024):.1f} MB"

    async def _row_counts(self, selection: dict) -> dict[str, int]:
        counts = {"products": 0, "sales": 0, "inventory": 0, "alerts": 0}
        pid = selection.get("products_import_id")
        sid = selection.get("sales_import_id")
        iid = selection.get("inventory_import_id")
        if pid:
            r = await self.session.execute(
                select(func.count()).select_from(Product).where(Product.import_id == pid)
            )
            counts["products"] = int(r.scalar() or 0)
        if sid:
            r = await self.session.execute(
                select(func.count()).select_from(SalesRecord).where(SalesRecord.import_id == sid)
            )
            counts["sales"] = int(r.scalar() or 0)
        if iid:
            r = await self.session.execute(
                select(func.count()).select_from(InventoryRecord).where(InventoryRecord.import_id == iid)
            )
            counts["inventory"] = int(r.scalar() or 0)
        r = await self.session.execute(
            select(func.count()).select_from(Alert).where(Alert.is_dismissed == False)  # noqa: E712
        )
        counts["alerts"] = int(r.scalar() or 0)
        return counts

    async def export_sales_csv_streaming(self) -> tuple[Path, str]:
        """Memory-safe CSV for large sales — chunked DB reads."""
        selection = await self._active_selection()
        sid = selection.get("sales_import_id")
        if not sid:
            raise ValueError("No sales dataset selected")

        ts = filename_timestamp()
        filename = f"commerceflow_sales_{ts}.csv"
        out = Path("data/exports/jobs") / filename
        out.parent.mkdir(parents=True, exist_ok=True)

        total = await self.session.execute(
            select(func.count()).select_from(SalesRecord).where(SalesRecord.import_id == sid)
        )
        total_n = int(total.scalar() or 0)
        chunk = self.settings.db_fetch_chunk_size
        headers = ["sku", "quantity", "revenue", "discount_amount", "order_id", "sold_at"]

        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            offset = 0
            while offset < total_n:
                result = await self.session.execute(
                    select(SalesRecord)
                    .where(SalesRecord.import_id == sid)
                    .order_by(SalesRecord.id)
                    .offset(offset)
                    .limit(chunk)
                )
                rows = result.scalars().all()
                if not rows:
                    break
                for s in rows:
                    writer.writerow({
                        "sku": s.sku,
                        "quantity": s.quantity,
                        "revenue": s.revenue,
                        "discount_amount": s.discount_amount,
                        "order_id": s.order_id,
                        "sold_at": s.sold_at.isoformat() if s.sold_at else "",
                    })
                offset += chunk
        return out, filename

    async def export_report(self, report_type: str, fmt: str = "csv") -> tuple[bytes, str, str]:
        if report_type == "enterprise":
            return await self.export_enterprise_workbook()

        selection = await self._active_selection()
        if report_type == "products":
            df = await self._products_df(selection)
        elif report_type == "inventory":
            df = await self._inventory_df(selection)
        elif report_type == "sales":
            df = await self._sales_df(selection)
        elif report_type == "alerts":
            df = await self._alerts_df()
        elif report_type == "profit_leakage":
            analysis = await self._load_analysis(selection)
            issues = analysis.get("profit_leakage", {}).get("issues", [])
            df = pd.DataFrame(issues)
        else:
            metrics, traces = await self._dashboard_metrics(selection)
            rows = []
            for key, val in metrics.model_dump().items():
                rows.append({"metric": key, "value": val if val is not None else "Not available"})
            for key, trace in traces.items():
                rows.append({
                    "metric": f"trace_{key}",
                    "formula": trace.get("formula"),
                    "dataset": trace.get("dataset"),
                    "row_count": trace.get("row_count"),
                })
            df = pd.DataFrame(rows)

        ts = filename_timestamp()
        filename = f"commerceflow_{report_type}_{ts}.{fmt}"
        content_type = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "json": "application/json",
        }.get(fmt, "application/octet-stream")

        if fmt == "csv":
            return df.to_csv(index=False).encode("utf-8"), filename, content_type
        if fmt == "xlsx":
            return self._dataframe_to_xlsx(df, report_type.replace("_", " ").title()), filename, content_type
        return (
            json.dumps(df.to_dict(orient="records"), indent=2, default=str).encode(),
            filename,
            content_type,
        )

    async def export_enterprise_workbook(self) -> tuple[bytes, str, str]:
        selection = await self._active_selection()
        analysis = await self._load_analysis(selection)
        metrics, traces = await self._dashboard_metrics(selection, analysis)

        products_df = await self._products_df(selection)
        alerts_df = await self._alerts_df()
        metadata = await self._enterprise_metadata(selection, alerts_df)
        inventory_df = await self._inventory_df(selection)
        sales_df = await self._sales_df(selection)
        metadata["chart_data"] = await self._chart_data(
            selection, analysis, products_df, inventory_df, sales_df
        )

        content = build_enterprise_workbook(
            metrics=metrics.model_dump(),
            metric_traces=traces,
            analysis=analysis,
            products_rows=products_df.to_dict(orient="records"),
            inventory_rows=inventory_df.to_dict(orient="records"),
            alerts_rows=alerts_df.to_dict(orient="records"),
            metadata=metadata,
        )
        return (
            content,
            enterprise_filename(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _dataframe_to_xlsx(self, df: pd.DataFrame, sheet_name: str) -> bytes:
        wb = Workbook()
        wb.remove(wb.active)
        write_dataframe_sheet(wb, sheet_name[:31], df)
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    async def _active_selection(self) -> dict:
        active = await ActiveDatasetService(self.session).get_active()
        return {
            "products_import_id": active.products_import_id,
            "sales_import_id": active.sales_import_id,
            "inventory_import_id": active.inventory_import_id,
        }

    async def _chart_data(
        self,
        selection: dict,
        analysis: dict,
        products_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        sales_df: pd.DataFrame,
    ) -> dict:
        from app.services.dataframe_loader import DataframeLoader
        from app.utils.chart_data_builder import (
            build_category_breakdown,
            build_inventory_risk_breakdown,
            build_revenue_trend,
            ensure_chart_payload,
            fallback_revenue_trend,
        )

        revenue_trend: list[dict] = []
        sid = selection.get("sales_import_id")
        if sid:
            daily = await DataframeLoader(self.session).load_sales_daily_revenue(sid, limit_days=90)
            revenue_trend = build_revenue_trend(daily)
        if not revenue_trend:
            revenue_trend = fallback_revenue_trend(sales_df)

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

    async def _enterprise_metadata(self, selection: dict, alerts_df: pd.DataFrame) -> dict:
        active = await ActiveDatasetService(self.session).get_active()
        counts = await self._row_counts(selection)
        generated = naive_local_now()

        def _dataset_label(item) -> str:
            if not item:
                return "Not selected"
            name = item.display_name or item.filename
            return f"{name} (Import #{item.id})"

        p_id = selection.get("products_import_id") or 0
        s_id = selection.get("sales_import_id") or 0
        i_id = selection.get("inventory_import_id") or 0
        analysis_id = f"CF-{p_id}-{s_id}-{i_id}-{generated.strftime('%Y%m%d%H%M%S')}"

        return {
            "generated_at": generated,
            "analysis_id": analysis_id,
            "engine_version": ENGINE_VERSION,
            "sales_dataset": _dataset_label(active.sales),
            "products_dataset": _dataset_label(active.products),
            "inventory_dataset": _dataset_label(active.inventory),
            "sales_rows": counts.get("sales", 0),
            "products_rows": counts.get("products", 0),
            "inventory_rows": counts.get("inventory", 0),
            "alerts_rows": len(alerts_df) if alerts_df is not None else counts.get("alerts", 0),
        }

    async def _load_analysis(self, selection: dict) -> dict:
        if not any(selection.values()):
            return {}
        orchestrator = AnalyticsOrchestrator(self.session)
        pipeline = await orchestrator.run_analysis_pipeline(use_cache=True, selection=selection)
        return pipeline.get("result") or {}

    async def _dashboard_metrics(self, selection: dict, analysis: dict | None = None):
        orchestrator = AnalyticsOrchestrator(self.session)
        bundle = await orchestrator._load_dataframes(selection)
        products_df, sales_df, inventory_df = bundle.products, bundle.sales, bundle.inventory
        if analysis is None:
            analysis = await self._load_analysis(selection)
        return MetricsEngine.compute(products_df, sales_df, inventory_df, analysis, selection)

    async def _products_df(self, selection: dict) -> pd.DataFrame:
        q = select(Product)
        pid = selection.get("products_import_id")
        if pid:
            q = q.where(Product.import_id == pid)
        else:
            return pd.DataFrame()
        result = await self.session.execute(q)
        return pd.DataFrame([self._product_row(p) for p in result.scalars().all()])

    async def _inventory_df(self, selection: dict) -> pd.DataFrame:
        q = select(InventoryRecord)
        iid = selection.get("inventory_import_id")
        if not iid:
            return pd.DataFrame()
        q = q.where(InventoryRecord.import_id == iid)
        result = await self.session.execute(q)
        return pd.DataFrame(
            [
                {
                    "sku": r.sku,
                    "quantity_on_hand": r.quantity_on_hand,
                    "inventory_health_score": r.inventory_health_score,
                    "risk_level": r.risk_level,
                    "days_in_stock": r.days_in_stock,
                    "days_cover": None,
                    "inventory_risk": r.risk_level,
                }
                for r in result.scalars().all()
            ]
        )

    async def _sales_df(self, selection: dict) -> pd.DataFrame:
        q = select(SalesRecord)
        sid = selection.get("sales_import_id")
        if not sid:
            return pd.DataFrame()
        q = q.where(SalesRecord.import_id == sid)
        result = await self.session.execute(q)
        return pd.DataFrame(
            [
                {
                    "sku": s.sku,
                    "quantity": s.quantity,
                    "revenue": s.revenue,
                    "discount_amount": s.discount_amount,
                    "order_id": s.order_id,
                    "sold_at": s.sold_at,
                }
                for s in result.scalars().all()
            ]
        )

    async def _alerts_df(self) -> pd.DataFrame:
        result = await self.session.execute(
            select(Alert).where(Alert.is_dismissed == False).order_by(Alert.created_at.desc())  # noqa: E712
        )
        return pd.DataFrame(
            [
                {
                    "severity": a.severity,
                    "alert_type": a.alert_type,
                    "title": a.title,
                    "message": a.message,
                    "created_at": a.created_at,
                    "sku": a.entity_id,
                }
                for a in result.scalars().all()
            ]
        )

    def _product_row(self, p: Product) -> dict:
        return {
            "sku": p.sku,
            "title": p.title,
            "category": p.category,
            "price": p.price,
            "cost": p.cost,
            "margin_pct": p.margin_pct,
            "health_score": p.health_score,
            "trend": p.trend_indicator,
            "revenue": None,
        }
