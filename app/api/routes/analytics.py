import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.datasets import AnalysisRunRequest
from app.services.active_dataset_service import ActiveDatasetService
from app.services.import_progress import has_imports_in_progress
from app.services.analysis_state import AnalysisStateService
from app.services.empty_analysis import EMPTY_MODULE_PAYLOADS
from app.services.dataset_catalog_service import DatasetCatalogService
from app.services.analytics_orchestrator import AnalysisPipelineError, AnalyticsOrchestrator
from app.services.business_insights import BusinessInsightsService
from app.services.usage_tracking_service import UsageTrackingService
from app.utils.cache import analytics_cache
from app.utils.json_safe import sanitize_for_json

logger = logging.getLogger("commerceflow.api")
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _error_response(exc: Exception, status: int = 500) -> JSONResponse:
    settings = get_settings()
    body: dict = {
        "success": False,
        "message": str(exc),
        "error_type": type(exc).__name__,
    }
    if isinstance(exc, AnalysisPipelineError):
        body["stages"] = exc.stages
        body["errors"] = exc.errors
        body["dataset_info"] = exc.dataset_info
        body["validation"] = exc.validation
        body["message"] = exc.message
    if settings.debug:
        body["traceback"] = traceback.format_exc()
    return JSONResponse(status_code=status, content=sanitize_for_json(body))


def _selection_from_request(body: AnalysisRunRequest) -> dict:
    return {
        "products_import_id": body.products_import_id,
        "sales_import_id": body.sales_import_id,
        "inventory_import_id": body.inventory_import_id,
    }


@router.get("/active-datasets")
async def get_active_datasets(db: AsyncSession = Depends(get_db)):
    service = ActiveDatasetService(db)
    return await service.get_active()


@router.put("/active-datasets")
async def set_active_datasets(
    products_import_id: int | None = None,
    sales_import_id: int | None = None,
    inventory_import_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = ActiveDatasetService(db)
    return await service.set_active(products_import_id, sales_import_id, inventory_import_id)


@router.post("/active-datasets/clear")
async def clear_active_datasets(db: AsyncSession = Depends(get_db)):
    """Clear staged selection so Run Your Analysis starts empty."""
    service = ActiveDatasetService(db)
    return await service.set_active(None, None, None)


@router.get("/dataset-info")
async def dataset_info(db: AsyncSession = Depends(get_db)):
    orchestrator = AnalyticsOrchestrator(db)
    return await orchestrator.get_dataset_info()


@router.post("/run")
async def run_analysis(body: AnalysisRunRequest, db: AsyncSession = Depends(get_db)):
    """Run analysis on explicitly selected import datasets."""
    selection = _selection_from_request(body)
    if not any(selection.values()):
        return JSONResponse(
            status_code=422,
            content=sanitize_for_json({
                "success": False,
                "message": "Select at least one dataset (products, sales, or inventory).",
            }),
        )

    catalog_svc = DatasetCatalogService(db)
    type_checks = [
        ("sales", body.sales_import_id),
        ("products", body.products_import_id),
        ("inventory", body.inventory_import_id),
    ]
    for expected, import_id in type_checks:
        if import_id and not await catalog_svc.validate_selection_for_type(import_id, expected):
            return JSONResponse(
                status_code=422,
                content=sanitize_for_json({
                    "success": False,
                    "message": f"Import #{import_id} is not valid as a {expected} dataset. Choose a file that contains {expected} data.",
                }),
            )

    if await has_imports_in_progress(db):
        return JSONResponse(
            status_code=409,
            content=sanitize_for_json({
                "success": False,
                "message": "Dataset import still in progress. Wait for import to complete before running analysis.",
            }),
        )

    active_svc = ActiveDatasetService(db)
    await active_svc.set_active(**selection)
    analytics_cache.invalidate()
    from app.services.export_job_service import export_jobs

    export_jobs.clear_all()

    orchestrator = AnalyticsOrchestrator(db)
    options = {
        "rebuild_dashboard": body.rebuild_dashboard,
        "regenerate_alerts": body.regenerate_alerts,
        "recalculate_inventory_risks": body.recalculate_inventory_risks,
        "export_report_after": body.export_report_after,
    }
    try:
        pipeline = await orchestrator.run_analysis_pipeline(
            use_cache=False,
            selection=selection,
            options=options,
        )
        tracker = UsageTrackingService(db)
        if pipeline.get("success"):
            await tracker.record(event_type="run_analysis_success", path="/dashboard")
        else:
            await tracker.record(
                event_type="run_analysis_fail",
                path="/dashboard",
                meta={"message": (pipeline.get("message") or "failed")[:200]},
            )
        status = 200 if pipeline.get("success") else 422
        return JSONResponse(status_code=status, content=sanitize_for_json(pipeline))
    except Exception as exc:
        logger.exception("Analysis pipeline crashed")
        await db.rollback()
        try:
            await UsageTrackingService(db).record(
                event_type="run_analysis_fail",
                path="/dashboard",
                meta={"message": str(exc)[:200]},
            )
            await db.commit()
        except Exception:
            pass
        return _error_response(exc)


@router.get("/full")
async def full_analysis(db: AsyncSession = Depends(get_db)):
    active = await ActiveDatasetService(db).get_active()
    if not active.has_selection:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "No active datasets. Run Your Analysis and select imports.",
            },
        )
    if not await AnalysisStateService(db).has_generated_analysis():
        return JSONResponse(
            status_code=422,
            content=sanitize_for_json({
                "success": False,
                "message": "No analysis generated yet. Run Your Analysis to build results.",
                "requires_analysis_generation": True,
            }),
        )
    orchestrator = AnalyticsOrchestrator(db)
    selection = {
        "products_import_id": active.products_import_id,
        "sales_import_id": active.sales_import_id,
        "inventory_import_id": active.inventory_import_id,
    }
    pipeline = await orchestrator.run_analysis_pipeline(use_cache=True, selection=selection)
    if not pipeline.get("success") and pipeline.get("result") is None:
        return JSONResponse(status_code=422, content=sanitize_for_json(pipeline))
    return sanitize_for_json(pipeline.get("result") or {})


@router.get("/public/preview")
async def public_analytics_preview():
    """Marketing-site preview KPIs (Atlas build-time snapshot — same schema as unified exports)."""
    from app.services.analytics_snapshot_service import AnalyticsSnapshotService

    return sanitize_for_json(AnalyticsSnapshotService.marketing_preview())


@router.get("/dashboard")
async def executive_dashboard(db: AsyncSession = Depends(get_db)):
    try:
        service = BusinessInsightsService(db)
        payload = await service.get_executive_dashboard()
        # Always return 200 with partial payload when possible — never blank the executive view.
        return sanitize_for_json(payload)
    except Exception as exc:
        logger.exception("Dashboard failed")
        return _error_response(exc)


@router.get("/products")
async def product_intelligence(db: AsyncSession = Depends(get_db)):
    return await _module_result(db, "product_intelligence")


@router.get("/profit-leakage")
async def profit_leakage(db: AsyncSession = Depends(get_db)):
    return await _module_result(db, "profit_leakage")


@router.get("/inventory")
async def inventory_health(db: AsyncSession = Depends(get_db)):
    return await _module_result(db, "inventory_risk")


@router.get("/data-quality")
async def data_quality(db: AsyncSession = Depends(get_db)):
    return await _module_result(db, "data_cleaning")


async def _module_result(db: AsyncSession, key: str):
    active = await ActiveDatasetService(db).get_active()
    if not active.has_selection:
        raise HTTPException(
            422,
            detail="No active datasets selected. Run Your Analysis to choose imports.",
        )
    if not await AnalysisStateService(db).has_generated_analysis():
        empty = dict(EMPTY_MODULE_PAYLOADS.get(key, {}))
        empty["requires_analysis_generation"] = True
        empty["has_generated_analysis"] = False
        return sanitize_for_json(empty)
    orchestrator = AnalyticsOrchestrator(db)
    selection = {
        "products_import_id": active.products_import_id,
        "sales_import_id": active.sales_import_id,
        "inventory_import_id": active.inventory_import_id,
    }
    pipeline = await orchestrator.run_analysis_pipeline(use_cache=True, selection=selection)
    if pipeline.get("result"):
        return pipeline["result"].get(key, {})
    raise HTTPException(422, detail=pipeline.get("message", "Analysis failed"))
