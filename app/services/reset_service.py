"""Enterprise data lifecycle: clear imports vs reset analysis (datasets preserved)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, func, or_, select, update
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
from app.services.reset_scope import ResetScope
from app.utils.active_config import get_active_analysis_config
from app.utils.cache import analytics_cache

logger = logging.getLogger("commerceflow.reset")


class ResetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def clear_imported_datasets(self, scope: ResetScope | None = None) -> dict:
        """
        Remove imported business data and upload artifacts for the given scope.
        Does not touch demo source files on disk (data/demo_companies/).
        """
        scope = scope or ResetScope(organization_id=None)
        counts = await self._delete_imported_data(scope)
        alerts_deleted = await self._delete_alerts(scope)
        snapshots_deleted = await self._delete_snapshots(scope)
        uploads_removed = await self._clear_uploads_for_scope(scope)
        exports_removed = self._clear_generated_exports() if scope.global_all else 0
        await self._reset_active_selection(scope)
        scores_cleared = await self._clear_persisted_scores(scope)
        await AnalysisStateService(self.session).clear_generated()
        analytics_cache.invalidate()
        if scope.global_all:
            self._clear_export_jobs()
        await self.session.flush()
        return {
            "success": True,
            "action": "clear_imported_datasets",
            "scope": scope.label,
            "message": f"Imported datasets cleared for {scope.label}. Upload new files to continue.",
            "deleted": {
                **counts,
                "alerts": alerts_deleted,
                "analytics_snapshots": snapshots_deleted,
            },
            "uploads_removed": uploads_removed,
            "exports_removed": exports_removed,
            "scores_cleared": scores_cleared,
            "datasets_preserved": False,
        }

    async def reset_analysis(self, scope: ResetScope | None = None) -> dict:
        """
        Clear generated intelligence for the scope — imported datasets stay intact.
        Does not run analysis; the user triggers Run Analysis when ready.
        """
        scope = scope or ResetScope(organization_id=None)
        alerts_deleted = await self._delete_alerts(scope)
        snapshots_deleted = await self._delete_snapshots(scope)
        exports_removed = self._clear_generated_exports() if scope.global_all else 0
        scores_cleared = await self._clear_persisted_scores(scope)
        analytics_cache.invalidate()
        if scope.global_all:
            self._clear_export_jobs()
        await AnalysisStateService(self.session).clear_generated()
        await self.session.flush()
        return {
            "success": True,
            "action": "reset_analysis",
            "scope": scope.label,
            "message": f"Analysis results cleared for {scope.label}. Run Your Analysis when you are ready.",
            "deleted": {
                "alerts": alerts_deleted,
                "analytics_snapshots": snapshots_deleted,
            },
            "scores_cleared": scores_cleared,
            "exports_removed": exports_removed,
            "datasets_preserved": True,
            "has_generated_analysis": False,
        }

    async def clear_import_history(self, scope: ResetScope | None = None) -> dict:
        return await self.clear_imported_datasets(scope)

    async def reset_demo_environment(self, scope: ResetScope | None = None) -> dict:
        return await self.reset_analysis(scope)

    async def rebuild_analytics_engine(self, *, regenerate: bool = False, scope: ResetScope | None = None) -> dict:
        return await self.reset_analysis(scope)

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

    async def _import_ids_for_scope(self, scope: ResetScope) -> list[int]:
        if scope.global_all:
            result = await self.session.execute(select(ImportRecord.id))
        elif scope.organization_id is None:
            result = await self.session.execute(
                select(ImportRecord.id).where(ImportRecord.organization_id.is_(None))
            )
        else:
            result = await self.session.execute(
                select(ImportRecord.id).where(ImportRecord.organization_id == scope.organization_id)
            )
        return [row[0] for row in result.all()]

    async def _delete_imported_data(self, scope: ResetScope) -> dict:
        if scope.global_all:
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

        import_ids = await self._import_ids_for_scope(scope)
        if not import_ids:
            return {
                "sales_records": 0,
                "inventory_records": 0,
                "products": 0,
                "import_records": 0,
            }

        sales = await self.session.execute(
            delete(SalesRecord).where(SalesRecord.import_id.in_(import_ids))
        )
        inventory = await self.session.execute(
            delete(InventoryRecord).where(InventoryRecord.import_id.in_(import_ids))
        )
        if scope.organization_id is None:
            product_filter = or_(
                Product.organization_id.is_(None),
                Product.import_id.in_(import_ids),
            )
        else:
            product_filter = or_(
                Product.organization_id == scope.organization_id,
                Product.import_id.in_(import_ids),
            )
        products = await self.session.execute(delete(Product).where(product_filter))
        imports = await self.session.execute(
            delete(ImportRecord).where(ImportRecord.id.in_(import_ids))
        )
        return {
            "sales_records": sales.rowcount or 0,
            "inventory_records": inventory.rowcount or 0,
            "products": products.rowcount or 0,
            "import_records": imports.rowcount or 0,
        }

    async def _delete_alerts(self, scope: ResetScope) -> int:
        if scope.global_all:
            stmt = delete(Alert)
        elif scope.organization_id is None:
            stmt = delete(Alert).where(Alert.organization_id.is_(None))
        else:
            stmt = delete(Alert).where(Alert.organization_id == scope.organization_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def _delete_snapshots(self, scope: ResetScope) -> int:
        if scope.global_all:
            stmt = delete(AnalyticsSnapshot)
        elif scope.organization_id is None:
            stmt = delete(AnalyticsSnapshot).where(AnalyticsSnapshot.organization_id.is_(None))
        else:
            stmt = delete(AnalyticsSnapshot).where(
                AnalyticsSnapshot.organization_id == scope.organization_id
            )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def _clear_persisted_scores(self, scope: ResetScope) -> dict:
        if scope.global_all:
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
        else:
            import_ids = await self._import_ids_for_scope(scope)
            if scope.organization_id is None:
                if import_ids:
                    product_filter = or_(
                        Product.organization_id.is_(None),
                        Product.import_id.in_(import_ids),
                    )
                else:
                    product_filter = Product.organization_id.is_(None)
            else:
                if import_ids:
                    product_filter = or_(
                        Product.organization_id == scope.organization_id,
                        Product.import_id.in_(import_ids),
                    )
                else:
                    product_filter = Product.organization_id == scope.organization_id
            products = await self.session.execute(
                update(Product).where(product_filter).values(
                    health_score=None,
                    performance_rank=None,
                    trend_indicator=None,
                )
            )
            if import_ids:
                inv_filter = InventoryRecord.import_id.in_(import_ids)
            else:
                return {
                    "products_reset": products.rowcount or 0,
                    "inventory_reset": 0,
                }
            inventory = await self.session.execute(
                update(InventoryRecord).where(inv_filter).values(
                    inventory_health_score=None,
                    risk_level=None,
                )
            )
        return {
            "products_reset": products.rowcount or 0,
            "inventory_reset": inventory.rowcount or 0,
        }

    async def _reset_active_selection(self, scope: ResetScope) -> None:
        config = await get_active_analysis_config(self.session)
        if scope.global_all:
            config.products_import_id = None
            config.sales_import_id = None
            config.inventory_import_id = None
            return

        import_ids = set(await self._import_ids_for_scope(scope))
        if config.products_import_id in import_ids:
            config.products_import_id = None
        if config.sales_import_id in import_ids:
            config.sales_import_id = None
        if config.inventory_import_id in import_ids:
            config.inventory_import_id = None

    async def _clear_uploads_for_scope(self, scope: ResetScope) -> int:
        if scope.global_all:
            return self._clear_upload_dir()

        import_ids = await self._import_ids_for_scope(scope)
        if not import_ids:
            return 0
        result = await self.session.execute(
            select(ImportRecord.filename).where(ImportRecord.id.in_(import_ids))
        )
        filenames = {row[0] for row in result.all() if row[0]}
        removed = 0
        upload_dir = self.settings.upload_dir
        for name in filenames:
            path = upload_dir / Path(name).name
            if path.is_file():
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not remove upload %s: %s", path, exc)
        return removed

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
