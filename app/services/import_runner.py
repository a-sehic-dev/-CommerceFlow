"""Background import execution with isolated DB sessions."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.constants import import_status as ST
from app.database import async_session_factory
from app.models.import_record import ImportRecord
from app.services.import_registry import claim_import
from app.services.import_service import ImportService
from app.utils.cache import analytics_cache
from app.utils.db_retry import commit_session
from app.utils.import_logger import log_import_failed, log_import_start, log_import_status

logger = logging.getLogger("commerceflow.import")


class ImportRunner:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}

    def is_running(self, import_id: int) -> bool:
        task = self._tasks.get(import_id)
        return task is not None and not task.done()

    def schedule(
        self,
        import_id: int,
        file_path: Path,
        source_type: str,
        *,
        forced_type: str | None = None,
    ) -> None:
        if self.is_running(import_id):
            return
        task = asyncio.create_task(
            self._run(import_id, file_path, source_type, forced_type=forced_type),
            name=f"import-{import_id}",
        )
        self._tasks[import_id] = task

        def _done(t: asyncio.Task) -> None:
            self._tasks.pop(import_id, None)
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                logger.error("Import task %s crashed: %s", import_id, exc)

        task.add_done_callback(_done)

    async def _run(
        self,
        import_id: int,
        file_path: Path,
        source_type: str,
        *,
        forced_type: str | None = None,
    ) -> None:
        async with async_session_factory() as session:
            service = ImportService(session)
            result = await session.execute(
                select(ImportRecord).where(ImportRecord.id == import_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return

            try:
                async with claim_import(import_id, record.filename):
                    log_import_start(import_id, record.filename, source_type, record.dataset_type or "auto")
                    record.status = ST.PROCESSING
                    await commit_session(session, label=f"import-{import_id}-processing")
                    log_import_status(import_id, ST.PROCESSING)

                    await service.process_file(
                        import_id,
                        file_path,
                        source_type,
                        forced_type=forced_type,
                    )
                    await commit_session(session, label=f"import-{import_id}-done")
                    analytics_cache.invalidate()
            except Exception as exc:
                await session.rollback()
                log_import_failed(import_id, exc)
                try:
                    await service.mark_failed(import_id, str(exc))
                    await commit_session(session, label=f"import-{import_id}-fail")
                except Exception as mark_exc:
                    logger.error("Could not mark import %s failed: %s", import_id, mark_exc)
                analytics_cache.invalidate()


import_runner = ImportRunner()
