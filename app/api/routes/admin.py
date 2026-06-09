from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.feedback import FeedbackEntry
from app.models.usage_event import UsageEvent
from app.services.demo_bootstrap import bootstrap_watch_if_needed, get_bootstrap_state
from app.services.demo_loader_service import DemoLoaderService, get_demo_companies
from app.services.reset_service import ResetService
from app.utils.founder_access import verify_founder_key
from app.utils.reset_scope_resolver import resolve_reset_scope

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/platform-status")
async def platform_status(db: AsyncSession = Depends(get_db)):
    return await ResetService(db).platform_status()


@router.get("/analytics-health")
async def analytics_health(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Raw DB counts (incl. /admin) — debug empty founder dashboard."""
    verify_founder_key(key)
    settings = get_settings()
    host = request.headers.get("host") or ""
    usage_total = int(
        await db.scalar(select(func.count()).select_from(UsageEvent)) or 0
    )
    feedback_total = int(
        await db.scalar(select(func.count()).select_from(FeedbackEntry)) or 0
    )
    last_usage = await db.scalar(select(func.max(UsageEvent.created_at)))
    last_feedback = await db.scalar(select(func.max(FeedbackEntry.created_at)))
    return {
        "service_host": host,
        "database_url": settings.database_url,
        "usage_events_total": usage_total,
        "feedback_entries_total": feedback_total,
        "last_usage_event_at": last_usage.isoformat() if last_usage else None,
        "last_feedback_at": last_feedback.isoformat() if last_feedback else None,
        "hint": (
            f"Guests and admin must use the same hostname (this service: {host}). "
            "commerceflow-1 and commerceflow-svfv are separate databases. "
            "Set the same USAGE_STATS_KEY on every Render service you use. "
            "Redeploy clears SQLite without a persistent disk."
        ),
    }


@router.post("/reset-insights")
async def reset_founder_insights(
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Clear all usage events and feedback (founder-only). Demo/import data unchanged."""
    verify_founder_key(key)
    usage_result = await db.execute(delete(UsageEvent))
    feedback_result = await db.execute(delete(FeedbackEntry))
    await db.commit()
    return {
        "success": True,
        "deleted": {
            "usage_events": int(usage_result.rowcount or 0),
            "feedback_entries": int(feedback_result.rowcount or 0),
        },
        "message": "Founder analytics reset. Run a fresh incognito test on this hostname.",
    }


@router.get("/feedback")
async def list_feedback(
    key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Founder inbox — all feedback stored in SQLite (requires USAGE_STATS_KEY)."""
    verify_founder_key(key)
    result = await db.execute(
        select(FeedbackEntry).order_by(FeedbackEntry.created_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "entries": [
            {
                "id": e.id,
                "rating": e.rating,
                "feedback_text": e.feedback_text,
                "email_optional": e.email_optional,
                "most_useful": e.most_useful,
                "session_id": e.session_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ],
    }


@router.post("/clear-imported-datasets")
async def clear_imported_datasets(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Remove imports for the signed-in org, guest workspace, or all data with founder key."""
    scope = resolve_reset_scope(request, key)
    result = await ResetService(db).clear_imported_datasets(scope)
    await db.commit()
    return result


@router.post("/reset-analysis")
async def reset_analysis(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Clear analysis results for the signed-in org, guest workspace, or all with founder key."""
    scope = resolve_reset_scope(request, key)
    result = await ResetService(db).reset_analysis(scope)
    await db.commit()
    return result


@router.post("/clear-import-history")
async def clear_import_history(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Deprecated alias — use clear-imported-datasets."""
    scope = resolve_reset_scope(request, key)
    result = await ResetService(db).clear_imported_datasets(scope)
    await db.commit()
    return result


@router.post("/reset-demo-environment")
async def reset_demo_environment(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Deprecated alias — use reset-analysis."""
    scope = resolve_reset_scope(request, key)
    result = await ResetService(db).reset_analysis(scope)
    await db.commit()
    return result


@router.post("/rebuild-analytics-engine")
async def rebuild_analytics_engine(
    request: Request,
    key: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Deprecated alias — use reset-analysis."""
    scope = resolve_reset_scope(request, key)
    result = await ResetService(db).reset_analysis(scope)
    await db.commit()
    return result


@router.post("/demo/bootstrap")
async def bootstrap_demo(db: AsyncSession = Depends(get_db)):
    """Idempotent: ensure watch guest workspace is imported and selected."""
    try:
        result = await bootstrap_watch_if_needed(db)
        await db.commit()
        result["bootstrap"] = get_bootstrap_state()
        return result
    except Exception as exc:
        await db.rollback()
        raise HTTPException(500, str(exc)) from exc


@router.post("/demo/load/{company}")
async def load_demo_company(company: str, db: AsyncSession = Depends(get_db)):
    companies = get_demo_companies()
    if company.lower() not in companies and not companies:
        raise HTTPException(404, "Evaluation workspace is temporarily unavailable.")
    try:
        service = DemoLoaderService(db)
        result = await service.load_company(company, fresh=False)
        await db.commit()
        return result
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(500, str(exc)) from exc
