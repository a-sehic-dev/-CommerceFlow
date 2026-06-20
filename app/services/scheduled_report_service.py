"""Weekly scheduled Excel report delivery."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.scheduled_report import ScheduledReport
from app.services.export_service import ExportService
from app.utils.app_timezone import naive_local_now
from app.utils.founder_email import send_email

logger = logging.getLogger("commerceflow.scheduled_reports")


class ScheduledReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_schedule(
        self,
        *,
        organization_id: int,
        email: str,
        day_of_week: int = 0,
        enabled: bool = True,
    ) -> ScheduledReport:
        if day_of_week < 0 or day_of_week > 6:
            raise ValueError("day_of_week must be 0 (Monday) through 6 (Sunday).")
        result = await self.session.execute(
            select(ScheduledReport).where(ScheduledReport.organization_id == organization_id)
        )
        schedule = result.scalar_one_or_none()
        if schedule:
            schedule.email = email.strip().lower()
            schedule.day_of_week = day_of_week
            schedule.enabled = enabled
        else:
            schedule = ScheduledReport(
                organization_id=organization_id,
                email=email.strip().lower(),
                day_of_week=day_of_week,
                enabled=enabled,
            )
            self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def get_schedule(self, organization_id: int) -> ScheduledReport | None:
        result = await self.session.execute(
            select(ScheduledReport).where(ScheduledReport.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def run_due_reports(self, *, force: bool = False) -> dict:
        now = naive_local_now()
        weekday = now.weekday()
        result = await self.session.execute(
            select(ScheduledReport).where(ScheduledReport.enabled.is_(True))
        )
        schedules = result.scalars().all()
        sent = []
        skipped = []

        for schedule in schedules:
            if not force and schedule.day_of_week != weekday:
                skipped.append({"organization_id": schedule.organization_id, "reason": "wrong_day"})
                continue
            if (
                not force
                and schedule.last_sent_at
                and schedule.last_sent_at > now - timedelta(days=6)
            ):
                skipped.append({"organization_id": schedule.organization_id, "reason": "already_sent"})
                continue

            org_name = await self.session.scalar(
                select(Organization.name).where(Organization.id == schedule.organization_id)
            )
            try:
                content, filename, _ = await ExportService(self.session).export_enterprise_workbook()
            except Exception as exc:
                logger.warning("Scheduled export failed org=%s: %s", schedule.organization_id, exc)
                skipped.append({"organization_id": schedule.organization_id, "reason": str(exc)})
                continue

            body = (
                f"Weekly CommerceFlow report for {org_name or 'your workspace'}.\n"
                f"Attached: {filename}\n\n"
                "Sign in to refresh analysis or change schedule settings."
            )
            ok = send_email(
                to=schedule.email,
                subject=f"[CommerceFlow] Weekly report — {org_name or 'Workspace'}",
                body=body,
                attachment=(
                    filename,
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
            if ok:
                schedule.last_sent_at = now
                sent.append({"organization_id": schedule.organization_id, "email": schedule.email})
            else:
                skipped.append({"organization_id": schedule.organization_id, "reason": "smtp_not_configured"})

        await self.session.flush()
        return {"sent": sent, "skipped": skipped, "checked": len(schedules)}
