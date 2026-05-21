"""In-process async export jobs with file-backed results (enterprise-scale safe)."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from app.utils.app_timezone import as_local_iso, now_local
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.database import async_session_factory
from app.services.export_service import ExportService
from app.utils.analysis_logger import log_exception, log_performance


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportJob:
    id: str
    report_type: str
    format: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = "Queued"
    filename: str | None = None
    file_path: str | None = None
    file_size_bytes: int = 0
    error: str | None = None
    created_at: str = field(default_factory=lambda: as_local_iso(now_local()) or "")
    completed_at: str | None = None
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "report_type": self.report_type,
            "format": self.format,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "file_size_human": _human_size(self.file_size_bytes),
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "download_url": f"/api/exports/jobs/{self.id}/download"
            if self.status == JobStatus.COMPLETED and self.file_path
            else None,
        }


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


class ExportJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ExportJob] = {}
        self._lock = asyncio.Lock()
        self._last_completed: ExportJob | None = None
        settings = get_settings()
        self.export_dir = Path("data/exports/jobs")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get(self, job_id: str) -> ExportJob | None:
        return self._jobs.get(job_id)

    def last_completed(self) -> ExportJob | None:
        return self._last_completed

    def clear_all(self) -> None:
        self._jobs.clear()
        self._last_completed = None

    async def create(self, report_type: str, fmt: str) -> ExportJob:
        job = ExportJob(id=uuid.uuid4().hex[:12], report_type=report_type, format=fmt)
        async with self._lock:
            self._jobs[job.id] = job
        asyncio.create_task(_run_job(job.id))
        return job

    async def set_progress(self, job_id: str, progress: int, message: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.progress = min(max(progress, 0), 100)
            job.message = message
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.RUNNING

    async def complete(self, job_id: str, path: Path, filename: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.message = "Export ready"
        job.file_path = str(path)
        job.filename = filename
        job.file_size_bytes = path.stat().st_size if path.exists() else 0
        job.completed_at = as_local_iso(now_local())
        self._last_completed = job

    async def fail(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = error
            job.message = "Export failed"
            job.completed_at = as_local_iso(now_local())


export_jobs = ExportJobStore()


async def _run_job(job_id: str) -> None:
    store = export_jobs
    job = store.get(job_id)
    if not job:
        return
    t0 = time.perf_counter()
    job.status = JobStatus.RUNNING
    try:
        async with async_session_factory() as session:
            service = ExportService(session)
            await store.set_progress(job_id, 5, "Preparing datasets…")
            await store.set_progress(job_id, 15, "Loading row counts…")

            if job.report_type == "enterprise":
                await store.set_progress(job_id, 35, "Running analytics modules…")
                await store.set_progress(job_id, 55, "Building enterprise workbook…")
                content, filename, _ = await service.export_enterprise_workbook()
            else:
                await store.set_progress(job_id, 40, f"Generating {job.report_type} export…")
                if job.format == "csv" and job.report_type == "sales":
                    path, filename = await service.export_sales_csv_streaming()
                    await store.set_progress(job_id, 95, "Finalizing file…")
                    await store.complete(job_id, path, filename)
                    job.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
                    log_performance("export_job", job_id=job_id, type=job.report_type, ms=job.duration_ms)
                    return
                content, filename, _ = await service.export_report(job.report_type, job.format)

            await store.set_progress(job_id, 85, "Writing file…")
            out_path = store.export_dir / f"{job_id}_{filename}"
            out_path.write_bytes(content)
            await store.complete(job_id, out_path, filename)
            job.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            log_performance(
                "export_job",
                job_id=job_id,
                type=job.report_type,
                format=job.format,
                bytes=job.file_size_bytes,
                ms=job.duration_ms,
            )
    except Exception as exc:
        log_exception(f"export_job_{job_id}", exc)
        await store.fail(job_id, str(exc))
        job = store.get(job_id)
        if job:
            job.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
