"""Enterprise data lifecycle: clear imports vs reset analysis (datasets preserved)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.active_analysis import ActiveAnalysisConfig
from app.models.alert import Alert
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.import_record import ImportRecord
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sales import SalesRecord
from app.services.analysis_state import AnalysisStateService
from app.utils.active_config import get_active_analysis_config
from app.utils.cache import analytics_cache

logger = logging.getLogger("commerceflow.reset")


class ResetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def clear_imported_datasets(self) -> dict:
        """
        Remove all imported business data and upload artifacts.
        Does not touch demo source files on disk (data/demo_companies/).
        """
        counts = await self._delete_imported_data()
        alerts_deleted = await self._delete_alerts()
        snapshots_deleted = await self._delete_snapshots()
        uploads_removed = self._clear_upload_dir()
        exports_removed = self._clear_generated_exports()
        await self._reset_active_selection()
        await self._clear_persisted_scores()
        await AnalysisStateService(self.session).clear_generated()
        analytics_cache.invalidate()
        self._clear_export_jobs()
        await self.session.flush()
        return {
            "success": True,
            "action": "clear_imported_datasets",
            "message": "Imported datasets cleared. Upload new files to continue.",
            "deleted": {
                **counts,
                "alerts": alerts_deleted,
                "analytics_snapshots": snapshots_deleted,
            },
            "uploads_removed": uploads_removed,
            "exports_removed": exports_removed,
            "datasets_preserved": False,
        }

    async def reset_analysis(self) -> dict:
        """
        Clear generated intelligence only — imported datasets and selection stay intact.
        Does not run analysis; the user triggers Run Analysis when ready.
        """
        alerts_deleted = await self._delete_alerts()
        snapshots_deleted = await self._delete_snapshots()
        exports_removed = self._clear_generated_exports()
        scores_cleared = await self._clear_persisted_scores()
        analytics_cache.invalidate()
        self._clear_export_jobs()
        await AnalysisStateService(self.session).clear_generated()
        await self.session.flush()
        return {
            "success": True,
            "action": "reset_analysis",
            "message": "Analysis results cleared. Run Your Analysis when you are ready to refresh the dashboard.",
            "deleted": {
                "alerts": alerts_deleted,
                "analytics_snapshots": snapshots_deleted,
            },
            "scores_cleared": scores_cleared,
            "exports_removed": exports_removed,
            "datasets_preserved": True,
            "has_generated_analysis": False,
        }

    # Backward-compatible aliases
    async def clear_import_history(self) -> dict:
        return await self.clear_imported_datasets()

    async def reset_demo_environment(self) -> dict:
        return await self.reset_analysis()

    async def rebuild_analytics_engine(self, *, regenerate: bool = False) -> dict:
        """Deprecated — use reset_analysis()."""
        return await self.reset_analysis()

    async def platform_status(self) -> dict:
        import_count = await self._scalar_count(ImportRecord)
        product_count = await self._scalar_count(Product)
        sales_count = await self._scalar_count(SalesRecord)
        alert_count = await self._scalar_count(Alert)
        active = await self._active_has_selection()
        has_analysis = await AnalysisStateService(self.session).has_generated_analysis()
        from app.services.demo_bootstrap import get_bootstrap_state, watch_workspace_ready
        from app.services.demo_loader_service import get_demo_companies

        demo_ready = await watch_workspace_ready(self.session)

        return {
            "has_imports": import_count > 0,
            "has_data": (product_count + sales_count) > 0,
            "has_active_analysis": active,
            "has_generated_analysis": has_analysis,
            "import_count": import_count,
            "alert_count": alert_count,
            "demo_files_ready": self._demo_files_ready(),
            "demo_companies": list(get_demo_companies().keys()),
            "demo_ready": demo_ready,
            "demo_bootstrap": get_bootstrap_state(),
        }

    async def _delete_imported_data(self) -> dict:
        sales = await self.session.execute(delete(SalesRecord))
        inventory = await self.session.execute(delete(InventoryRecord))
        products = await self.session.execute(delete(Product))
        imports = await self.session.execute(delete(ImportRecord))
        return {
            "sales_records": sales.rowcount or 0,
            "inventory_records": inventory.rowcount or 0,
            "products": products.rowcount or 0,
            "import_records": imports.rowcount or 0,
        }

    async def _delete_alerts(self) -> int:
        result = await self.session.execute(delete(Alert))
        return result.rowcount or 0

    async def _delete_snapshots(self) -> int:
        result = await self.session.execute(delete(AnalyticsSnapshot))
        return result.rowcount or 0

    async def _clear_persisted_scores(self) -> dict:
        products = await self.session.execute(
            update(Product).values(
                health_score=None,
                performance_rank=None,
                trend_indicator=None,
            )
        )
        inventory = await self.session.execute(
            update(InventoryRecord).values(
                inventory_health_score=None,
                risk_level=None,
            )
        )
        return {
            "products_reset": products.rowcount or 0,
            "inventory_reset": inventory.rowcount or 0,
        }

    async def _reset_active_selection(self) -> None:
        config = await get_active_analysis_config(self.session)
        config.products_import_id = None
        config.sales_import_id = None
        config.inventory_import_id = None

    def _clear_upload_dir(self) -> int:
        removed = 0
        upload_dir = self.settings.upload_dir
        if not upload_dir.exists():
            return 0
        for path in upload_dir.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not remove upload %s: %s", path, exc)
        return removed

    def _clear_generated_exports(self) -> int:
        export_root = self.settings.upload_dir.parent / "exports"
        if not export_root.exists():
            return 0
        removed = 0
        for path in export_root.rglob("*"):
            if path.is_file():
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not remove export %s: %s", path, exc)
        return removed

    def _clear_export_jobs(self) -> None:
        try:
            from app.services.export_job_service import export_jobs

            export_jobs.clear_all()
        except Exception as exc:
            logger.debug("Export job store clear skipped: %s", exc)

    def _demo_files_ready(self) -> bool:
        from app.services.demo_loader_service import get_demo_companies

        return bool(get_demo_companies())

    async def _scalar_count(self, model) -> int:
        result = await self.session.execute(select(func.count()).select_from(model))
        return int(result.scalar() or 0)

    async def _active_has_selection(self) -> bool:
        result = await self.session.execute(
            select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        if not config:
            return False
        return any(
            [
                config.products_import_id,
                config.sales_import_id,
                config.inventory_import_id,
            ]
        )
