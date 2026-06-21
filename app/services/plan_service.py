"""Resolve organization plan and enforce feature limits."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.store_connection import StoreConnection
from app.utils.plan_limits import PlanLimits, get_plan_limits, normalize_plan, plan_limits_payload


class PlanService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_org_plan(self, organization_id: int) -> str:
        plan = await self.session.scalar(
            select(Organization.plan).where(Organization.id == organization_id)
        )
        return normalize_plan(plan)

    async def get_limits(self, organization_id: int) -> PlanLimits:
        return get_plan_limits(await self.get_org_plan(organization_id))

    async def limits_payload(self, organization_id: int) -> dict:
        return plan_limits_payload(await self.get_org_plan(organization_id))

    async def connected_store_count(self, organization_id: int) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(StoreConnection)
            .where(
                StoreConnection.organization_id == organization_id,
                StoreConnection.status == "connected",
            )
        )
        return int(count or 0)

    async def ensure_live_sync(self, organization_id: int) -> PlanLimits:
        limits = await self.get_limits(organization_id)
        if not limits.live_sync:
            raise HTTPException(
                403,
                detail="Live store sync requires Pro or higher. Upgrade in the sidebar.",
            )
        return limits

    async def ensure_can_add_store(self, organization_id: int) -> PlanLimits:
        limits = await self.ensure_live_sync(organization_id)
        used = await self.connected_store_count(organization_id)
        if used >= limits.max_stores:
            raise HTTPException(
                403,
                detail=(
                    f"Store limit reached ({limits.max_stores} on {limits.label}). "
                    "Upgrade to Ultra for multiple stores."
                ),
            )
        return limits

    async def ensure_team_invites(self, organization_id: int) -> PlanLimits:
        limits = await self.get_limits(organization_id)
        if not limits.team_invites:
            raise HTTPException(
                403,
                detail="Team invites require Team or Ultra. Upgrade in the sidebar.",
            )
        return limits

    async def ensure_weekly_email(self, organization_id: int) -> PlanLimits:
        limits = await self.get_limits(organization_id)
        if not limits.weekly_email:
            raise HTTPException(
                403,
                detail="Weekly email reports require Pro or higher. Upgrade in the sidebar.",
            )
        return limits

    async def ensure_pdf_export(self, organization_id: int) -> PlanLimits:
        limits = await self.get_limits(organization_id)
        if not limits.pdf_export:
            raise HTTPException(
                403,
                detail="Executive PDF export requires Pro or higher. Upgrade in the sidebar.",
            )
        return limits
