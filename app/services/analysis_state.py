"""Tracks whether the user has run analysis on the current dataset selection."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_analysis import ActiveAnalysisConfig
from app.utils.active_config import get_active_analysis_config
from app.utils.analysis_selection import selection_fingerprint
from app.utils.app_timezone import naive_local_now


class AnalysisStateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _config(self) -> ActiveAnalysisConfig:
        return await get_active_analysis_config(self.session)

    def selection_key_for(self, config: ActiveAnalysisConfig) -> str | None:
        if not any(
            (
                config.products_import_id,
                config.sales_import_id,
                config.inventory_import_id,
            )
        ):
            return None
        return selection_fingerprint(
            {
                "products_import_id": config.products_import_id,
                "sales_import_id": config.sales_import_id,
                "inventory_import_id": config.inventory_import_id,
            }
        )

    async def current_selection_key(self) -> str | None:
        return self.selection_key_for(await self._config())

    async def has_generated_analysis(self) -> bool:
        config = await self._config()
        if config.analysis_generated_at is None:
            return False
        stored = config.analysis_selection_key
        current = self.selection_key_for(config)
        return bool(stored and current and stored == current)

    async def mark_generated(self) -> None:
        config = await self._config()
        config.analysis_generated_at = naive_local_now()
        config.analysis_selection_key = self.selection_key_for(config)
        await self.session.flush()

    async def clear_generated(self) -> None:
        config = await self._config()
        config.analysis_generated_at = None
        config.analysis_selection_key = None
        await self.session.flush()
