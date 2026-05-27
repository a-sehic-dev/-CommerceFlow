from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_analysis import ActiveAnalysisConfig
from app.schemas.datasets import ActiveDatasetsResponse, ImportCatalogItem
from app.services.dataset_catalog_service import DatasetCatalogService


class ActiveDatasetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_config(self) -> ActiveAnalysisConfig:
        result = await self.session.execute(
            select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        if not config:
            config = ActiveAnalysisConfig(id=1)
            self.session.add(config)
            await self.session.flush()
        return config

    async def get_active(self) -> ActiveDatasetsResponse:
        config = await self._get_config()
        products = sales = inventory = None

        if config.products_import_id:
            products = await self._import_item(config.products_import_id)
        if config.sales_import_id:
            sales = await self._import_item(config.sales_import_id)
        if config.inventory_import_id:
            inventory = await self._import_item(config.inventory_import_id)

        has = any([config.products_import_id, config.sales_import_id, config.inventory_import_id])

        from app.services.analysis_state import AnalysisStateService

        state = AnalysisStateService(self.session)
        has_analysis = await state.has_generated_analysis()

        return ActiveDatasetsResponse(
            products_import_id=config.products_import_id,
            sales_import_id=config.sales_import_id,
            inventory_import_id=config.inventory_import_id,
            products=products,
            sales=sales,
            inventory=inventory,
            has_selection=has,
            has_generated_analysis=has_analysis,
            analysis_generated_at=config.analysis_generated_at if has_analysis else None,
        )

    async def set_active(
        self,
        products_import_id: int | None = None,
        sales_import_id: int | None = None,
        inventory_import_id: int | None = None,
    ) -> ActiveDatasetsResponse:
        from app.services.analysis_state import AnalysisStateService
        from app.utils.analysis_selection import selection_fingerprint
        from app.utils.cache import analytics_cache

        config = await self._get_config()
        previous_key = selection_fingerprint(
            {
                "products_import_id": config.products_import_id,
                "sales_import_id": config.sales_import_id,
                "inventory_import_id": config.inventory_import_id,
            }
        )
        next_key = selection_fingerprint(
            {
                "products_import_id": products_import_id,
                "sales_import_id": sales_import_id,
                "inventory_import_id": inventory_import_id,
            }
        )
        config.products_import_id = products_import_id
        config.sales_import_id = sales_import_id
        config.inventory_import_id = inventory_import_id
        if previous_key != next_key:
            await AnalysisStateService(self.session).clear_generated()
            analytics_cache.invalidate()
            from app.services.export_job_service import export_jobs

            export_jobs.clear_all()
        await self.session.flush()
        return await self.get_active()

    async def _import_item(self, import_id: int) -> ImportCatalogItem | None:
        return await DatasetCatalogService(self.session).item_for_import_id(import_id)

    def selection_dict(self, config: ActiveAnalysisConfig) -> dict:
        return {
            "products_import_id": config.products_import_id,
            "sales_import_id": config.sales_import_id,
            "inventory_import_id": config.inventory_import_id,
        }
