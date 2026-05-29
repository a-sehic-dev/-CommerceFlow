"""Import execution — runs inline on the request so Render does not drop background tasks."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from sqlalchemy import select

from app.constants import import_status as ST
from app.database import async_session_factory
from app.models.import_record import ImportRecord
from app.services.import_registry import claim_import, release_import
from app.services.import_service import ImportService
from app.utils.cache import analytics_cache
from app.utils.db_retry import commit_session
from app.utils.import_logger import log_import_failed, log_import_start, log_import_status

logger = logging.getLogger("commerceflow.import")


class ImportRunner:
    async def run_import(
        self,
        import_id: int,
        file_path: Path,
        source_type: str,
        *,
        forced_type: str | None = None,
    ) -> None:
        """Process import to completion in the current worker (reliable on Render)."""
        logger.info(
            "import_run_start id=%s path=%s source=%s forced=%s",
            import_id,
            file_path.name,
            source_type,
            forced_type or "",
        )
        if not file_path.is_file():
            await self._fail_missing(import_id, f"Upload file missing on disk: {file_path}")
            return
        await self._run(import_id, file_path, source_type, forced_type=forced_type)
        logger.info("import_run_finished id=%s", import_id)

    def schedule(
        self,
        import_id: int,
        file_path: Path,
        source_type: str,
        *,
        forced_type: str | None = None,
    ) -> None:
        """Deprecated: use run_import (await) so work is not lost after HTTP response."""
        logger.warning(
            "import_schedule_deprecated id=%s — callers should await run_import",
            import_id,
        )

    async def _fail_missing(self, import_id: int, message: str) -> None:
        logger.error("import_abort id=%s %s", import_id, message)
        async with async_session_factory() as session:
            service = ImportService(session)
            try:
                await service.mark_failed(import_id, message)
                await session.commit()
            except Exception as mark_exc:
                logger.error("import_mark_failed_error id=%s %s", import_id, mark_exc)

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
                await self._fail_missing(
                    import_id,
                    "Import record not found after upload (database commit issue).",
                )
                return

            try:
                async with claim_import(import_id, record.filename):
                    log_import_start(
                        import_id, record.filename, source_type, record.dataset_type or "auto"
                    )
                    logger.info("import_processing id=%s file_saved=yes", import_id)
                    record.status = ST.PROCESSING
                    await commit_session(session, label=f"import-{import_id}-processing")
                    log_import_status(import_id, ST.PROCESSING)

                    effective_forced = forced_type
                    if not effective_forced and record.dataset_type in (
                        "products",
                        "sales",
                        "inventory",
                    ):
                        effective_forced = record.dataset_type

                    await service.process_file(
                        import_id,
                        file_path,
                        source_type,
                        forced_type=effective_forced,
                    )
                    await commit_session(session, label=f"import-{import_id}-done")
                    logger.info("import_dataset_saved id=%s status=committed", import_id)
                    analytics_cache.invalidate()
            except Exception as exc:
                await session.rollback()
                log_import_failed(import_id, exc)
                logger.error(
                    "import_exception id=%s %s\n%s",
                    import_id,
                    exc,
                    traceback.format_exc(),
                )
                try:
                    await service.mark_failed(import_id, str(exc))
                    await commit_session(session, label=f"import-{import_id}-fail")
                except Exception as mark_exc:
                    logger.error("Could not mark import %s failed: %s", import_id, mark_exc)
                analytics_cache.invalidate()
            finally:
                await release_import(import_id, record.filename)


import_runner = ImportRunner()
