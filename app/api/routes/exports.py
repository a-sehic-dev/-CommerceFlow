from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.analytics import ExportJobRequest, ExportRequest
from app.services.export_job_service import export_jobs
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/meta")
async def export_metadata(db: AsyncSession = Depends(get_db)):
    service = ExportService(db)
    return await service.get_export_meta()


@router.post("/jobs")
async def create_export_job(body: ExportJobRequest, db: AsyncSession = Depends(get_db)):
    meta = await ExportService(db).get_export_meta()
    if not meta.get("has_selection") and body.report_type != "alerts":
        raise HTTPException(422, detail="Select datasets in Run Analysis before exporting.")
    job = await export_jobs.create(body.report_type, body.format)
    return {"success": True, "job": job.to_dict()}


@router.get("/jobs/{job_id}")
async def get_export_job(job_id: str):
    job = export_jobs.get(job_id)
    if not job:
        raise HTTPException(404, detail="Export job not found")
    return job.to_dict()


@router.get("/jobs/{job_id}/download")
async def download_export_job(job_id: str):
    job = export_jobs.get(job_id)
    if not job or job.status.value != "completed" or not job.file_path:
        raise HTTPException(404, detail="Export not ready")
    path = job.file_path
    return FileResponse(
        path,
        filename=job.filename or "export.bin",
        media_type="application/octet-stream",
    )


@router.post("/{report_type}")
async def export_report(report_type: str, body: ExportRequest, db: AsyncSession = Depends(get_db)):
    """Synchronous export for smaller datasets; prefer /jobs for enterprise workbook."""
    service = ExportService(db)
    meta = await service.get_export_meta()
    if meta.get("async_recommended") and report_type in ("enterprise", "sales"):
        job = await export_jobs.create(report_type, body.format)
        return {"success": True, "async": True, "job": job.to_dict()}

    content, filename, content_type = await service.export_report(report_type, body.format)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
