from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.analytics import ExportJobRequest, ExportRequest
from app.services.export_job_service import export_jobs
from app.services.export_service import ExportService
from app.services.plan_service import PlanService
from app.utils.session_auth import get_session_from_request

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/latest/download")
async def download_latest_export(db: AsyncSession = Depends(get_db)):
    """Deprecated — exports must be generated from Export Center for the current analysis."""
    resolved = await ExportService(db).resolve_latest_workbook_path()
    if not resolved:
        raise HTTPException(
            404,
            detail="No export for the current analysis. Run Your Analysis, then generate a workbook in Export Center.",
        )
    path, filename = resolved
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/meta")
async def export_metadata(db: AsyncSession = Depends(get_db)):
    service = ExportService(db)
    return await service.get_export_meta()


@router.post("/jobs")
async def create_export_job(body: ExportJobRequest, db: AsyncSession = Depends(get_db)):
    from app.services.analytics_snapshot_service import AnalyticsSnapshotService

    meta = await ExportService(db).get_export_meta()
    if not meta.get("has_selection") and body.report_type != "alerts":
        raise HTTPException(422, detail="Select datasets in Run Your Analysis before exporting.")
    if not meta.get("has_generated_analysis"):
        raise HTTPException(
            422,
            detail="Run Your Analysis before exporting. Exports always reflect the latest analysis run.",
        )
    fingerprint = await AnalyticsSnapshotService(db).current_analysis_id()
    job = await export_jobs.create(
        body.report_type,
        body.format,
        analysis_fingerprint=fingerprint,
    )
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
async def export_report(report_type: str, body: ExportRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Synchronous export for smaller datasets; prefer /jobs for enterprise workbook."""
    service = ExportService(db)
    meta = await service.get_export_meta()
    if meta.get("async_recommended") and report_type in ("enterprise", "sales"):
        job = await export_jobs.create(report_type, body.format)
        return {"success": True, "async": True, "job": job.to_dict()}

    if report_type == "executive_pdf" or (report_type == "enterprise" and body.format == "pdf"):
        auth = get_session_from_request(request)
        if auth:
            await PlanService(db).ensure_pdf_export(auth.organization_id)
        from app.services.analytics_snapshot_service import AnalyticsSnapshotService
        from app.services.pdf_export_service import build_executive_pdf

        unified = await AnalyticsSnapshotService(db).get_current(rebuild_if_missing=True)
        if not unified:
            raise HTTPException(422, detail="Run Your Analysis before exporting PDF.")
        metrics = unified.get("metrics") or {}
        content, filename = build_executive_pdf(
            company_name="CommerceFlow Workspace",
            metrics=metrics,
            analysis_id=unified.get("analysis_id"),
        )
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    content, filename, content_type = await service.export_report(report_type, body.format)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
