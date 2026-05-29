"""Mark abandoned import rows so uploads are not blocked forever."""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import import_status as ST
from app.models.import_record import ImportRecord
from app.utils.app_timezone import naive_local_now

logger = logging.getLogger("commerceflow.import")

STALE_MINUTES = 3


async def recover_stale_imports(session: AsyncSession) -> int:
    """Fail imports stuck in importing/processing (browser closed, server restart, lock)."""
    cutoff = naive_local_now() - timedelta(minutes=STALE_MINUTES)
    result = await session.execute(
        select(ImportRecord).where(
            ImportRecord.status.in_(tuple(ST.IN_PROGRESS)),
            ImportRecord.started_at < cutoff,
        )
    )
    records = list(result.scalars().all())
    for record in records:
        record.status = ST.FAILED
        record.completed_at = naive_local_now()
        record.error_count = max(1, record.error_count or 0)
        record.errors_json = json.dumps(
            [
                "Import timed out or was interrupted. Delete this entry and upload again "
                "(select Products / Inventory / Sales type before upload for small files)."
            ]
        )
        logger.warning("Recovered stale import #%s (%s)", record.id, record.filename)
    if records:
        await session.flush()
    return len(records)
