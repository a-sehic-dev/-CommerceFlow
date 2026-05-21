"""Tracks whether the user has run analysis on the current dataset selection."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_analysis import ActiveAnalysisConfig
from app.utils.app_timezone import naive_local_now


class AnalysisStateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _config(self) -> ActiveAnalysisConfig:
        result = await self.session.execute(
            select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        if not config:
            config = ActiveAnalysisConfig(id=1)
            self.session.add(config)
            await self.session.flush()
        return config

    async def has_generated_analysis(self) -> bool:
        config = await self._config()
        return config.analysis_generated_at is not None

    async def mark_generated(self) -> None:
        config = await self._config()
        config.analysis_generated_at = naive_local_now()
        await self.session.flush()

    async def clear_generated(self) -> None:
        config = await self._config()
        config.analysis_generated_at = None
        await self.session.flush()
