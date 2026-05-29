from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.usage_tracking_service import UsageTrackingService
from app.utils.founder_access import verify_founder_key

router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageTrackRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    path: str | None = Field(default=None, max_length=256)
    session_id: str | None = Field(default=None, max_length=120)
    meta: dict | None = None


@router.post("/track")
async def track_usage(body: UsageTrackRequest, db: AsyncSession = Depends(get_db)):
    """Fire-and-forget client event (non-blocking for the UI)."""
    await UsageTrackingService(db).record(
        event_type=body.event_type,
        path=body.path,
        session_id=body.session_id,
        meta=body.meta,
    )
    await db.commit()
    return {"ok": True}


@router.get("/summary")
async def usage_summary(
    key: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    verify_founder_key(key)
    return await UsageTrackingService(db).summary(days=days)
