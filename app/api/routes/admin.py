from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feedback import FeedbackEntry
from app.utils.founder_access import verify_founder_key
from app.services.demo_bootstrap import bootstrap_atlas_if_needed, get_bootstrap_state
from app.services.demo_loader_service import DemoLoaderService, get_demo_companies
from app.services.reset_service import ResetService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/platform-status")
async def platform_status(db: AsyncSession = Depends(get_db)):
    return await ResetService(db).platform_status()


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
async def clear_imported_datasets(db: AsyncSession = Depends(get_db)):
    """Remove imports, uploads, history, and selection. Does not delete demo source files."""
    result = await ResetService(db).clear_imported_datasets()
    await db.commit()
    return result


@router.post("/reset-analysis")
async def reset_analysis(db: AsyncSession = Depends(get_db)):
    """Clear metrics, alerts, cache, and reports; keep imported datasets. Does not re-run analysis."""
    result = await ResetService(db).reset_analysis()
    await db.commit()
    return result


@router.post("/clear-import-history")
async def clear_import_history(db: AsyncSession = Depends(get_db)):
    """Deprecated alias — use clear-imported-datasets."""
    result = await ResetService(db).clear_imported_datasets()
    await db.commit()
    return result


@router.post("/reset-demo-environment")
async def reset_demo_environment(db: AsyncSession = Depends(get_db)):
    """Deprecated alias — use reset-analysis."""
    result = await ResetService(db).reset_analysis()
    await db.commit()
    return result


@router.post("/rebuild-analytics-engine")
async def rebuild_analytics_engine(db: AsyncSession = Depends(get_db)):
    """Deprecated alias — use reset-analysis."""
    result = await ResetService(db).reset_analysis()
    await db.commit()
    return result


@router.post("/demo/bootstrap")
async def bootstrap_demo(db: AsyncSession = Depends(get_db)):
    """Idempotent: ensure Atlas guest workspace is imported and selected."""
    try:
        result = await bootstrap_atlas_if_needed(db)
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
        result = await service.load_company(company, fresh=True)
        await db.commit()
        return result
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(500, str(exc)) from exc
