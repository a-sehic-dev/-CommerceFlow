import json
import time
from app.utils.app_timezone import as_local_iso, now_local
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.engines.data_cleaning import DataCleaningEngine
from app.engines.inventory_risk import InventoryRiskEngine
from app.engines.product_intelligence import ProductIntelligenceEngine
from app.engines.profit_leakage import ProfitLeakageEngine
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.services.active_dataset_service import ActiveDatasetService
from app.services.analysis_validation import validate_datasets
from app.services.dataframe_loader import DataframeLoader
from app.services.dataset_bundle import DatasetBundle
from app.utils.analysis_logger import log_dataset_info, log_exception, log_performance, log_stage
from app.utils.dataframe_ops import memory_mb
from app.utils.cache import analytics_cache
from app.utils.json_safe import sanitize_for_json


from app.utils.analysis_selection import analysis_cache_key as _cache_key

STAGE_LABELS = {
    "loading_dataset": "Loading dataset…",
    "validating_schema": "Validating schema…",
    "product_intelligence": "Building product intelligence…",
    "profit_leakage": "Detecting profit leakage…",
    "inventory_risk": "Analyzing inventory risk…",
    "data_cleaning": "Running data quality checks…",
    "persisting_scores": "Persisting scores to database…",
    "saving_snapshot": "Saving analytics snapshot…",
    "caching_results": "Updating dashboard cache…",
}


class AnalyticsOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_engine = ProductIntelligenceEngine()
        self.profit_engine = ProfitLeakageEngine()
        self.inventory_engine = InventoryRiskEngine()
        self.cleaning_engine = DataCleaningEngine()
        self.stages: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def _record_stage(
        self,
        name: str,
        status: str,
        message: str = "",
        duration_ms: float | None = None,
        detail: dict | None = None,
    ) -> None:
        entry = {
            "name": name,
            "label": STAGE_LABELS.get(name, name),
            "status": status,
            "message": message,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        }
        if detail:
            entry["detail"] = detail
        self.stages.append(entry)
        log_stage(name, f"{status}: {message}")

    def _record_error(self, stage: str, exc: Exception, include_traceback: bool = True) -> None:
        import traceback as tb

        err = {
            "stage": stage,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        if include_traceback and get_settings().debug:
            err["traceback"] = tb.format_exc()
        self.errors.append(err)
        log_exception(stage, exc)

    async def run_full_analysis(self, use_cache: bool = True) -> dict:
        """Backward-compatible: returns analysis payload only."""
        pipeline = await self.run_analysis_pipeline(use_cache=use_cache)
        if not pipeline["success"] and not pipeline.get("result"):
            raise AnalysisPipelineError(
                message=pipeline.get("message", "Analysis failed"),
                stages=pipeline["stages"],
                errors=pipeline["errors"],
                dataset_info=pipeline.get("dataset_info", {}),
                validation=pipeline.get("validation", {}),
            )
        return pipeline["result"]

    async def run_analysis_pipeline(
        self,
        use_cache: bool = False,
        selection: dict[str, int | None] | None = None,
        options: dict[str, bool] | None = None,
    ) -> dict:
        self.stages = []
        self.errors = []
        options = options or {}
        t0 = time.perf_counter()

        if selection is None:
            active = ActiveDatasetService(self.session)
            config = await active._get_config()
            selection = active.selection_dict(config)

        if not any(selection.get(k) for k in ("products_import_id", "sales_import_id", "inventory_import_id")):
            return self._failure_response(
                "No datasets selected. Choose sales, products, and/or inventory imports before running analysis.",
                {"selection": selection},
            )

        cache_key = _cache_key(selection)
        if use_cache:
            cached = analytics_cache.get(cache_key)
            if cached:
                self._record_stage("caching_results", "completed", "Served from cache", 0)
                return {
                    "success": True,
                    "cached": True,
                    "stages": self.stages,
                    "errors": [],
                    "dataset_info": {"from_cache": True, "selection": selection},
                    "validation": {},
                    "result": cached,
                    "active_selection": selection,
                    "message": "Analysis loaded from cache",
                }

        products_df = sales_df = inventory_df = pd.DataFrame()
        dataset_info: dict[str, Any] = {}

        # ── Stage 1: Load dataset ──
        stage = "loading_dataset"
        t_stage = time.perf_counter()
        try:
            bundle = await self._load_dataframes(selection)
            products_df, sales_df, inventory_df = bundle.products, bundle.sales, bundle.inventory
            dataset_info = bundle.info
            log_dataset_info(
                stage,
                dataset_info["row_counts"]["products"],
                dataset_info["row_counts"]["sales"],
                dataset_info["row_counts"]["inventory"],
                dataset_info.get("selected_imports"),
                dataset_info.get("database_path"),
                load_modes=dataset_info.get("load_modes"),
                memory_mb=dataset_info.get("memory_mb_after_load"),
            )
            self._record_stage(
                stage,
                "completed",
                f"Loaded {dataset_info['row_counts']['products']} products, "
                f"{dataset_info['row_counts']['sales']} sales, "
                f"{dataset_info['row_counts']['inventory']} inventory rows",
                (time.perf_counter() - t_stage) * 1000,
                dataset_info["row_counts"],
            )
        except Exception as exc:
            self._record_stage(stage, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(stage, exc)
            return self._failure_response("Failed to load dataset from database", dataset_info)

        # ── Stage 2: Validate schema ──
        stage = "validating_schema"
        t_stage = time.perf_counter()
        validation = validate_datasets(
            products_df,
            sales_df,
            inventory_df,
            selection=selection,
        )
        try:
            if validation.warnings:
                for w in validation.warnings:
                    log_stage(stage, f"warning: {w}")
            if validation.errors:
                for err in validation.errors:
                    log_stage(stage, f"error: {err}")
            self._record_stage(
                stage,
                "completed" if validation.valid else "failed",
                validation.errors[0]
                if validation.errors
                else ("; ".join(validation.warnings[:3]) if validation.warnings else "Schema OK"),
                (time.perf_counter() - t_stage) * 1000,
                validation.to_dict(),
            )
        except Exception as exc:
            self._record_stage(stage, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(stage, exc)

        if not validation.valid:
            message = validation.errors[0] if validation.errors else "Dataset validation failed."
            return self._failure_response(
                message,
                dataset_info,
                validation=validation.to_dict(),
            )

        result: dict[str, Any] = {
            "product_intelligence": self._empty_product_intel(),
            "profit_leakage": {"issues": [], "total_estimated_leakage": 0, "issue_count": 0, "critical_count": 0, "recommendations": []},
            "inventory_risk": {"alerts": [], "reorder_suggestions": [], "summary": {}},
            "data_cleaning": {"issues": [], "quality_score": 100, "issue_count": 0},
            "generated_at": as_local_iso(now_local()),
        }

        # ── Stage 3–6: Analytics modules (isolated failures) ──
        result["product_intelligence"] = await self._run_module(
            "product_intelligence",
            lambda: self._run_product_intelligence(products_df, sales_df),
            result["product_intelligence"],
        )
        result["data_cleaning"] = await self._run_module(
            "data_cleaning",
            lambda: self.cleaning_engine.analyze(products_df) if not products_df.empty else result["data_cleaning"],
            result["data_cleaning"],
        )
        data_issues = result["data_cleaning"].get("issues", [])
        result["profit_leakage"] = await self._run_module(
            "profit_leakage",
            lambda: self.profit_engine.analyze(
                products_df,
                sales_df,
                inventory_df,
                data_quality_issues=data_issues,
            ),
            result["profit_leakage"],
        )
        result["inventory_risk"] = await self._run_module(
            "inventory_risk",
            lambda: self._run_inventory(inventory_df, sales_df, products_df),
            result["inventory_risk"],
        )

        # ── Stage 7: Persist scores ──
        stage = "persisting_scores"
        t_stage = time.perf_counter()
        try:
            product_intel_raw = await self._safe_product_intel_df(products_df, sales_df)
            inv_raw = await self._safe_inventory_df(inventory_df, sales_df, products_df)
            await self._persist_product_scores(product_intel_raw.get("products"))
            await self._persist_inventory_scores(inv_raw.get("inventory"))
            self._record_stage(stage, "completed", "Scores saved", (time.perf_counter() - t_stage) * 1000)
        except Exception as exc:
            self._record_stage(stage, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(stage, exc)

        # Serialize for JSON
        serialized = {
            "product_intelligence": self._serialize_product_intel(
                await self._safe_product_intel_df(products_df, sales_df)
            ),
            "profit_leakage": sanitize_for_json(result["profit_leakage"]),
            "inventory_risk": self._serialize_inventory(result["inventory_risk"]),
            "data_cleaning": sanitize_for_json(result["data_cleaning"]),
            "generated_at": as_local_iso(now_local()),
        }

        # ── Stage 8: Snapshot ──
        stage = "saving_snapshot"
        t_stage = time.perf_counter()
        try:
            await self._save_snapshot("full_analysis", serialized)
            self._record_stage(stage, "completed", "Snapshot stored", (time.perf_counter() - t_stage) * 1000)
        except Exception as exc:
            self._record_stage(stage, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(stage, exc)

        # ── Stage 9: Cache ──
        stage = "caching_results"
        t_stage = time.perf_counter()
        try:
            analytics_cache.set(cache_key, serialized)
            analytics_cache.set("full_analysis", serialized)
            self._record_stage(stage, "completed", "Cache updated", (time.perf_counter() - t_stage) * 1000)
        except Exception as exc:
            self._record_stage(stage, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(stage, exc)

        post_actions: list[str] = []
        if options.get("regenerate_alerts"):
            try:
                from app.services.alert_service import AlertService

                alerts = await AlertService(self.session).generate_from_analysis()
                post_actions.append(f"Generated {len(alerts)} alerts")
            except Exception as exc:
                self._record_error("regenerate_alerts", exc)
                post_actions.append(f"Alert generation failed: {exc}")

        export_path = None
        if options.get("export_report_after"):
            try:
                from app.services.export_service import ExportService

                content, filename, _ = await ExportService(self.session).export_report("summary", "xlsx")
                export_dir = get_settings().upload_dir.parent / "exports"
                export_dir.mkdir(parents=True, exist_ok=True)
                export_path = str(export_dir / filename)
                Path(export_path).write_bytes(content)
                post_actions.append(f"Exported {filename}")
            except Exception as exc:
                self._record_error("export_report", exc)
                post_actions.append(f"Export failed: {exc}")

        failed_modules = [e["stage"] for e in self.errors]
        success = len(failed_modules) == 0 or any(
            s["status"] == "completed"
            for s in self.stages
            if s["name"] in ("product_intelligence", "profit_leakage", "inventory_risk", "data_cleaning")
        )

        total_ms = (time.perf_counter() - t0) * 1000
        log_performance(
            "analysis_pipeline",
            duration_ms=round(total_ms, 1),
            memory_mb=round(memory_mb(), 1),
            failed_modules=failed_modules,
        )
        if success and serialized:
            from app.services.analysis_state import AnalysisStateService
            from app.services.analytics_snapshot_service import AnalyticsSnapshotService

            try:
                snap_svc = AnalyticsSnapshotService(self.session)
                unified = await snap_svc.build_unified(selection, analysis=serialized)
                await snap_svc.persist_unified(selection, unified)
                await AnalysisStateService(self.session).mark_generated()
            except Exception as exc:
                await self.session.rollback()
                self._record_error("unified_snapshot", exc)
                success = False
                self._record_stage(
                    "unified_snapshot",
                    "failed",
                    f"Dashboard snapshot failed: {exc}",
                )
        return sanitize_for_json({
            "success": success,
            "cached": False,
            "stages": self.stages,
            "errors": self.errors,
            "dataset_info": dataset_info,
            "validation": validation.to_dict(),
            "result": serialized,
            "active_selection": selection,
            "post_actions": post_actions,
            "export_path": export_path,
            "message": (
                f"Analysis completed in {total_ms:.0f}ms"
                + (f" ({len(failed_modules)} module warning(s))" if failed_modules else "")
            ),
            "failed_modules": failed_modules,
        })

    async def _run_module(self, name: str, fn, fallback: dict) -> dict:
        t_stage = time.perf_counter()
        try:
            out = fn()
            if hasattr(out, "__await__"):
                out = await out
            self._record_stage(name, "completed", "OK", (time.perf_counter() - t_stage) * 1000)
            return out
        except Exception as exc:
            self._record_stage(name, "failed", str(exc), (time.perf_counter() - t_stage) * 1000)
            self._record_error(name, exc)
            return fallback

    async def _run_product_intelligence(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> dict:
        raw = self.product_engine.analyze(products_df, sales_df)
        return self._serialize_product_intel(raw)

    async def _safe_product_intel_df(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> dict:
        return self.product_engine.analyze(products_df, sales_df)

    async def _run_inventory(
        self, inventory_df: pd.DataFrame, sales_df: pd.DataFrame, products_df: pd.DataFrame
    ) -> dict:
        raw = self.inventory_engine.analyze(inventory_df, sales_df, products_df)
        return self._serialize_inventory(raw)

    async def _safe_inventory_df(
        self, inventory_df: pd.DataFrame, sales_df: pd.DataFrame, products_df: pd.DataFrame
    ) -> dict:
        return self.inventory_engine.analyze(inventory_df, sales_df, products_df)

    def _failure_response(
        self,
        message: str,
        dataset_info: dict,
        validation: dict | None = None,
    ) -> dict:
        return sanitize_for_json({
            "success": False,
            "cached": False,
            "stages": self.stages,
            "errors": self.errors,
            "dataset_info": dataset_info,
            "validation": validation or {},
            "result": None,
            "message": message,
            "failed_modules": [e["stage"] for e in self.errors],
        })

    def _empty_product_intel(self) -> dict:
        return {
            "top_sellers": [],
            "worst_performers": [],
            "fast_rising": [],
            "declining": [],
            "unstable": [],
            "summary": {"avg_health_score": 0, "rising_count": 0, "declining_count": 0},
        }

    async def _load_dataframes(self, selection: dict[str, int | None]) -> DatasetBundle:
        return await DataframeLoader(self.session).load(selection)

    async def get_dataset_info(self, selection: dict | None = None) -> dict:
        if selection is None:
            active = ActiveDatasetService(self.session)
            config = await active._get_config()
            selection = active.selection_dict(config)
        if not any(selection.values()):
            return {"selection": selection, "row_counts": {"products": 0, "sales": 0, "inventory": 0}}
        bundle = await self._load_dataframes(selection)
        return bundle.info

    async def _persist_product_scores(self, products_df: pd.DataFrame | None) -> None:
        if products_df is None or products_df.empty or "sku" not in products_df.columns:
            return
        result = await self.session.execute(select(Product))
        db_products = {p.sku: p for p in result.scalars().all()}
        for _, row in products_df.iterrows():
            p = db_products.get(row.get("sku"))
            if not p:
                continue
            hs = row.get("health_score", 0)
            pr = row.get("performance_rank", 0)
            p.health_score = None if pd.isna(hs) else float(hs)
            p.performance_rank = None if pd.isna(pr) else int(pr)
            p.trend_indicator = str(row.get("trend_indicator", "stable"))
        await self.session.flush()

    async def _persist_inventory_scores(self, inventory_df: pd.DataFrame | None) -> None:
        if inventory_df is None or inventory_df.empty:
            return
        result = await self.session.execute(select(InventoryRecord))
        records = {r.sku: r for r in result.scalars().all()}
        for _, row in inventory_df.iterrows():
            r = records.get(row.get("sku"))
            if not r:
                continue
            hs = row.get("inventory_health_score", 0)
            r.inventory_health_score = None if pd.isna(hs) else float(hs)
            r.risk_level = str(row.get("risk_level", "low"))
        await self.session.flush()

    async def _save_snapshot(self, snapshot_type: str, payload: dict) -> None:
        self.session.add(
            AnalyticsSnapshot(
                snapshot_type=snapshot_type,
                payload_json=json.dumps(sanitize_for_json(payload), default=str),
            )
        )
        await self.session.flush()

    def _serialize_product_intel(self, data: dict) -> dict:
        out = {k: v for k, v in data.items() if k != "products"}
        return sanitize_for_json(out)

    def _serialize_inventory(self, data: dict) -> dict:
        inv = data.get("inventory")
        out = dict(data)
        if isinstance(inv, pd.DataFrame) and not inv.empty:
            out["inventory_sample"] = inv.head(50).to_dict(orient="records")
        out.pop("inventory", None)
        return sanitize_for_json(out)


class AnalysisPipelineError(Exception):
    def __init__(
        self,
        message: str,
        stages: list | None = None,
        errors: list | None = None,
        dataset_info: dict | None = None,
        validation: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.stages = stages or []
        self.errors = errors or []
        self.dataset_info = dataset_info or {}
        self.validation = validation or {}
