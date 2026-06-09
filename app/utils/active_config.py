"""Singleton active_analysis_config row (safe under concurrent requests)."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_analysis import ActiveAnalysisConfig
from app.utils.app_timezone import naive_local_now
from app.utils.database_url import is_sqlite_url
from app.config import get_settings


async def get_active_analysis_config(session: AsyncSession) -> ActiveAnalysisConfig:
    """Return the singleton config row, creating it if missing."""
    result = await session.execute(
        select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
    )
    config = result.scalar_one_or_none()
    if config is not None:
        return config

    now = naive_local_now()
    try:
        if is_sqlite_url(get_settings().database_url):
            insert_sql = (
                "INSERT OR IGNORE INTO active_analysis_config (id, updated_at) "
                "VALUES (1, :updated_at)"
            )
        else:
            insert_sql = (
                "INSERT INTO active_analysis_config (id, updated_at) "
                "VALUES (1, :updated_at) ON CONFLICT (id) DO NOTHING"
            )
        await session.execute(text(insert_sql), {"updated_at": now})
        await session.flush()
    except IntegrityError:
        await session.rollback()

    result = await session.execute(
        select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
    )
    config = result.scalar_one_or_none()
    if config is not None:
        return config

    config = ActiveAnalysisConfig(id=1)
    session.add(config)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
        )
        config = result.scalar_one()
    return config
