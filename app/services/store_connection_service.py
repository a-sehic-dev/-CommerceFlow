"""Shared store connection queries (multi-store on Ultra)."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store_connection import StoreConnection


def store_slug(domain: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")
    return value[:48] or "store"


class StoreConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_connections(self, organization_id: int, *, provider: str | None = None) -> list[StoreConnection]:
        query = select(StoreConnection).where(StoreConnection.organization_id == organization_id)
        if provider:
            query = query.where(StoreConnection.provider == provider)
        query = query.order_by(StoreConnection.created_at.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_domain(self, organization_id: int, provider: str, store_domain: str) -> StoreConnection | None:
        result = await self.session.execute(
            select(StoreConnection).where(
                StoreConnection.organization_id == organization_id,
                StoreConnection.provider == provider,
                StoreConnection.store_domain == store_domain,
            )
        )
        return result.scalar_one_or_none()

    async def connected_count(self, organization_id: int) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(StoreConnection)
            .where(
                StoreConnection.organization_id == organization_id,
                StoreConnection.status == "connected",
            )
        )
        return int(count or 0)
