"""Lightweight product usage events stored in SQLite (no third-party analytics)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent
from app.utils.app_timezone import naive_local_now


class UsageTrackingService:
    ALLOWED_EVENTS = frozenset({
        "page_view",
        "landing_view",
        "load_demo",
        "run_analysis_start",
        "run_analysis_success",
        "run_analysis_fail",
        "export_enterprise",
        "export_report",
        "feedback_submit",
        "assistant_chat",
    })

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        event_type: str,
        path: str | None = None,
        session_id: str | None = None,
        meta: dict | None = None,
    ) -> None:
        event_type = (event_type or "").strip().lower()[:64]
        if event_type not in self.ALLOWED_EVENTS:
            return
        path = (path or "")[:256] or None
        session_id = (session_id or "")[:120] or None
        meta_json = None
        if meta:
            try:
                meta_json = json.dumps(meta, default=str)[:2000]
            except (TypeError, ValueError):
                meta_json = None
        self.session.add(
            UsageEvent(
                event_type=event_type,
                path=path,
                session_id=session_id,
                meta_json=meta_json,
                created_at=naive_local_now(),
            )
        )
        await self.session.flush()

    async def summary(self, *, days: int = 30) -> dict:
        since = naive_local_now() - timedelta(days=max(1, min(days, 90)))
        total = await self.session.scalar(
            select(func.count()).select_from(UsageEvent).where(UsageEvent.created_at >= since)
        )
        sessions = await self.session.scalar(
            select(func.count(func.distinct(UsageEvent.session_id)))
            .select_from(UsageEvent)
            .where(UsageEvent.created_at >= since, UsageEvent.session_id.isnot(None))
        )
        by_event_rows = await self.session.execute(
            select(UsageEvent.event_type, func.count())
            .where(UsageEvent.created_at >= since)
            .group_by(UsageEvent.event_type)
            .order_by(func.count().desc())
        )
        by_path_rows = await self.session.execute(
            select(UsageEvent.path, func.count())
            .where(UsageEvent.created_at >= since, UsageEvent.path.isnot(None))
            .group_by(UsageEvent.path)
            .order_by(func.count().desc())
            .limit(12)
        )
        recent_rows = await self.session.execute(
            select(UsageEvent)
            .where(UsageEvent.created_at >= since)
            .order_by(UsageEvent.created_at.desc())
            .limit(40)
        )
        funnel = {
            "landing_view": await self._count_event("landing_view", since),
            "load_demo": await self._count_event("load_demo", since),
            "run_analysis_success": await self._count_event("run_analysis_success", since),
            "export_enterprise": await self._count_event("export_enterprise", since),
            "feedback_submit": await self._count_event("feedback_submit", since),
        }
        return {
            "period_days": days,
            "since": since.isoformat(),
            "total_events": int(total or 0),
            "unique_sessions": int(sessions or 0),
            "by_event": [{"event": r[0], "count": r[1]} for r in by_event_rows.all()],
            "by_path": [{"path": r[0], "count": r[1]} for r in by_path_rows.all()],
            "funnel": funnel,
            "recent": [
                {
                    "event_type": e.event_type,
                    "path": e.path,
                    "session_id": e.session_id,
                    "meta_json": e.meta_json,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in recent_rows.scalars().all()
            ],
        }

    async def _count_event(self, event_type: str, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.created_at >= since, UsageEvent.event_type == event_type)
        )
        return int(value or 0)
