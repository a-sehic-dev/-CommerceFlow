from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.scheduled_report_service import ScheduledReportService
from app.utils.permissions import ROLE_ANALYST, require_role
from app.utils.session_auth import require_session
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ScheduleRequest(BaseModel):
    email: str = Field(..., max_length=256)
    day_of_week: int = Field(default=0, ge=0, le=6)
    enabled: bool = True


@router.get("/schedule")
async def get_report_schedule(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    schedule = await ScheduledReportService(db).get_schedule(auth.organization_id)
    if not schedule:
        return {"enabled": False, "email": auth.email, "day_of_week": 0}
    return {
        "enabled": schedule.enabled,
        "email": schedule.email,
        "day_of_week": schedule.day_of_week,
        "last_sent_at": schedule.last_sent_at.isoformat() if schedule.last_sent_at else None,
    }


@router.post("/schedule")
async def set_report_schedule(request: Request, body: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_ANALYST)
    try:
        schedule = await ScheduledReportService(db).upsert_schedule(
            organization_id=auth.organization_id,
            email=body.email,
            day_of_week=body.day_of_week,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return {
        "success": True,
        "enabled": schedule.enabled,
        "email": schedule.email,
        "day_of_week": schedule.day_of_week,
    }
