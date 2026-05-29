import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.import_record import ImportRecord
from app.schemas.analytics import BulkDeleteImportsRequest, ConfirmDatasetTypeRequest, ImportStatusResponse
from app.schemas.datasets import ImportCatalogResponse
from app.constants import import_status as ST
from app.services.dataset_catalog_service import DatasetCatalogService
from app.services.import_progress import has_imports_in_progress
from app.services.import_registry import (
    has_active_imports,
    is_filename_busy,
    release_all_imports,
    release_import,
)
from app.services.import_runner import import_runner
from app.services.import_service import ImportService
from app.services.import_stale_recovery import recover_stale_imports
from app.utils.cache import analytics_cache
from app.utils.dataset_display import (
    dataset_source_label,
    detect_company_name,
    is_internal_dataset,
    resolve_display_name,
)
from app.utils.file_types import is_supported_upload

router = APIRouter(prefix="/api/imports", tags=["imports"])


def _detection_reason(record: ImportRecord) -> str | None:
    if not record.detection_scores_json:
        return None
    try:
        payload = json.loads(record.detection_scores_json)
        if isinstance(payload, dict):
            return payload.get("reason")
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _import_response(record: ImportRecord) -> ImportStatusResponse:
    return ImportStatusResponse(
        id=record.id,
        filename=record.filename,
        display_name=resolve_display_name(record.filename, record.dataset_type),
        company_name=detect_company_name(record.filename),
        source_label=dataset_source_label(record.filename),
        source_type=record.source_type,
        dataset_type=record.dataset_type or "unknown",
        detection_confidence=record.detection_confidence,
        detection_reason=_detection_reason(record),
        needs_type_confirmation=bool(record.needs_type_confirmation),
        products_imported=record.products_imported or 0,
        sales_imported=record.sales_imported or 0,
        inventory_imported=record.inventory_imported or 0,
        status=record.status,
        row_count=record.row_count,
        success_count=record.success_count,
        error_count=record.error_count,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


@router.get("/catalog")
async def import_catalog(db: AsyncSession = Depends(get_db)) -> ImportCatalogResponse:
    return await DatasetCatalogService(db).list_catalog()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    source_type: str = Form(default="generic"),
    dataset_type: str = Form(default="auto"),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    if not is_supported_upload(file.filename):
        raise HTTPException(400, "Supported formats: CSV, XLSX, XLS")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_upload_size_mb}MB limit")

    await recover_stale_imports(db)
    in_progress = await db.execute(
        select(ImportRecord.id).where(ImportRecord.status.in_(tuple(ST.IN_PROGRESS))).limit(1)
    )
    if not in_progress.scalar_one_or_none() and await has_active_imports():
        await release_all_imports()
    if await has_active_imports():
        raise HTTPException(
            409,
            "Another import is already in progress. Wait a moment or delete the stuck import in history.",
        )
    if await is_filename_busy(file.filename):
        raise HTTPException(409, f"Import already running for: {file.filename}")

    dest = settings.upload_dir / file.filename
    dest.write_bytes(content)

    service = ImportService(db)
    record = await service.create_import(file.filename, source_type, dataset_type=dataset_type)
    await db.flush()

    import_runner.schedule(record.id, dest, source_type)
    return _import_response(record)


@router.get("/{import_id}/status")
async def import_status(import_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ImportRecord).where(ImportRecord.id == import_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Import not found")
    return _import_response(record)


@router.post("/{import_id}/cancel")
async def cancel_import(import_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a stuck import as failed so new uploads can proceed."""
    await recover_stale_imports(db)
    service = ImportService(db)
    record = await service.get_import(import_id)
    if not record:
        raise HTTPException(404, "Import not found")
    if record.status not in ST.IN_PROGRESS:
        return {"success": True, "message": "Import is not in progress", "id": import_id}
    await service.mark_failed(import_id, "Import cancelled by user.")
    await release_import(import_id, record.filename)
    await db.commit()
    analytics_cache.invalidate()
    return {"success": True, "message": "Import cancelled", "id": import_id}


@router.get("/in-progress")
async def imports_in_progress(db: AsyncSession = Depends(get_db)):
    await recover_stale_imports(db)
    result = await db.execute(
        select(ImportRecord).where(ImportRecord.status.in_(tuple(ST.IN_PROGRESS)))
    )
    records = result.scalars().all()
    return {"in_progress": [_import_response(r) for r in records], "count": len(records)}


@router.get("/history")
async def import_history(db: AsyncSession = Depends(get_db)):
    await recover_stale_imports(db)
    service = ImportService(db)
    records = await service.list_imports()
    return [_import_response(r) for r in records if not is_internal_dataset(r.filename)]


@router.delete("/{import_id}")
async def delete_import(import_id: int, db: AsyncSession = Depends(get_db)):
    service = ImportService(db)
    if not await service.delete_import(import_id):
        raise HTTPException(404, "Import not found")
    analytics_cache.invalidate()
    return {"success": True, "message": "Dataset removed", "id": import_id}


@router.post("/bulk-delete")
async def bulk_delete_imports(body: BulkDeleteImportsRequest, db: AsyncSession = Depends(get_db)):
    service = ImportService(db)
    deleted = await service.delete_imports(body.import_ids)
    analytics_cache.invalidate()
    return {"success": True, "deleted": deleted, "message": f"Removed {deleted} dataset(s)"}


@router.post("/{import_id}/confirm-type")
async def confirm_dataset_type(
    import_id: int,
    body: ConfirmDatasetTypeRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    result = await db.execute(select(ImportRecord).where(ImportRecord.id == import_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Import not found")

    dest = settings.upload_dir / record.filename
    if not dest.exists():
        raise HTTPException(404, "Uploaded file no longer available; please re-upload")

    if await has_active_imports():
        raise HTTPException(409, "Another import is already in progress.")

    service = ImportService(db)
    record = await service.confirm_dataset_type(
        import_id, body.dataset_type, dest, record.source_type
    )
    record.status = ST.IMPORTING
    await db.flush()
    import_runner.schedule(import_id, dest, record.source_type, forced_type=body.dataset_type)
    return _import_response(record)
