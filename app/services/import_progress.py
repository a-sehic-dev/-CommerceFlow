"""Query helpers for in-flight imports."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.import_status import IN_PROGRESS
from app.models.import_record import ImportRecord


async def has_imports_in_progress(session: AsyncSession) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(ImportRecord)
        .where(ImportRecord.status.in_(tuple(IN_PROGRESS)))
    )
    return int(result.scalar() or 0) > 0
