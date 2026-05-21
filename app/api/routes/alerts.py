from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.analytics import AlertResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/generate")
async def generate_alerts(db: AsyncSession = Depends(get_db)):
    service = AlertService(db)
    alerts = await service.generate_from_analysis()
    return {"generated": len(alerts)}


@router.get("")
async def list_alerts(
    severity: str | None = Query(None),
    alert_type: str | None = Query(None),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    alerts = await service.list_alerts(severity=severity, alert_type=alert_type, unread_only=unread_only)
    return [
        AlertResponse(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            title=a.title,
            message=a.message,
            score=a.score,
            is_read=a.is_read,
            created_at=a.created_at,
        )
        for a in alerts
    ]


@router.patch("/{alert_id}/read")
async def mark_read(alert_id: int, db: AsyncSession = Depends(get_db)):
    service = AlertService(db)
    alert = await service.mark_read(alert_id)
    if not alert:
        return {"error": "Not found"}
    return {"ok": True}


@router.patch("/{alert_id}/dismiss")
async def dismiss(alert_id: int, db: AsyncSession = Depends(get_db)):
    service = AlertService(db)
    alert = await service.dismiss(alert_id)
    if not alert:
        return {"error": "Not found"}
    return {"ok": True}
