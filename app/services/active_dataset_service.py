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

        return ActiveDatasetsResponse(
            products_import_id=config.products_import_id,
            sales_import_id=config.sales_import_id,
            inventory_import_id=config.inventory_import_id,
            products=products,
            sales=sales,
            inventory=inventory,
            has_selection=has,
            has_generated_analysis=config.analysis_generated_at is not None,
            analysis_generated_at=config.analysis_generated_at,
        )

    async def set_active(
        self,
        products_import_id: int | None = None,
        sales_import_id: int | None = None,
        inventory_import_id: int | None = None,
    ) -> ActiveDatasetsResponse:
        config = await self._get_config()
        config.products_import_id = products_import_id
        config.sales_import_id = sales_import_id
        config.inventory_import_id = inventory_import_id
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
