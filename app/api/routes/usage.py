from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.usage_tracking_service import UsageTrackingService

router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageTrackRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    path: str | None = Field(default=None, max_length=256)
    session_id: str | None = Field(default=None, max_length=120)
    meta: dict | None = None


def _verify_stats_key(key: str | None) -> None:
    settings = get_settings()
    expected = (settings.usage_stats_key or "").strip()
    if not expected:
        if settings.app_env == "development" or settings.debug:
            return
        raise HTTPException(
            403,
            detail="Usage insights are disabled. Set USAGE_STATS_KEY in the server environment.",
        )
    if not key or key != expected:
        raise HTTPException(403, detail="Invalid or missing insights key.")


@router.post("/track")
async def track_usage(body: UsageTrackRequest, db: AsyncSession = Depends(get_db)):
    """Fire-and-forget client event (non-blocking for the UI)."""
    await UsageTrackingService(db).record(
        event_type=body.event_type,
        path=body.path,
        session_id=body.session_id,
        meta=body.meta,
    )
    return {"ok": True}


@router.get("/summary")
async def usage_summary(
    key: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    _verify_stats_key(key)
    return await UsageTrackingService(db).summary(days=days)
