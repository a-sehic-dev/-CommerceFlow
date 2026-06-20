from __future__ import annotations

import logging

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.organization import Organization

log = logging.getLogger("commerceflow")


class StripeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        if self.settings.stripe_secret_key:
            stripe.api_key = self.settings.stripe_secret_key

    def _ensure_enabled(self) -> None:
        if not self.settings.stripe_secret_key:
            raise HTTPException(503, "Stripe is not configured.")

    async def get_org(self, organization_id: int) -> Organization:
        result = await self.db.execute(select(Organization).where(Organization.id == organization_id))
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(404, "Organization not found.")
        return org

    async def ensure_customer(self, org: Organization) -> str:
        self._ensure_enabled()
        if org.stripe_customer_id:
            return org.stripe_customer_id

        customer = stripe.Customer.create(
            name=org.name,
            metadata={"organization_id": str(org.id)},
        )
        org.stripe_customer_id = customer["id"]
        await self.db.flush()
        return org.stripe_customer_id

    async def create_checkout_session(self, *, org: Organization, price_id: str, success_url: str, cancel_url: str) -> str:
        self._ensure_enabled()
        customer_id = await self.ensure_customer(org)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            allow_promotion_codes=True,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"organization_id": str(org.id)},
        )
        return session["url"]

    async def create_billing_portal_session(self, *, org: Organization, return_url: str) -> str:
        self._ensure_enabled()
        if not org.stripe_customer_id:
            raise HTTPException(422, "No Stripe customer exists for this workspace yet.")
        portal = stripe.billing_portal.Session.create(customer=org.stripe_customer_id, return_url=return_url)
        return portal["url"]

    async def apply_subscription_from_stripe(self, *, organization_id: int, subscription: dict) -> None:
        org = await self.get_org(organization_id)
        org.stripe_subscription_id = subscription.get("id")
        org.stripe_subscription_status = subscription.get("status")

        # pick the first price id for now
        items = (subscription.get("items") or {}).get("data") or []
        price_id = None
        if items:
            price_id = ((items[0] or {}).get("price") or {}).get("id")
        org.stripe_price_id = price_id

        # map known prices to plan slug
        pro = self.settings.stripe_price_pro
        team = self.settings.stripe_price_team
        if team and price_id == team:
            org.plan = "team"
        elif pro and price_id == pro:
            org.plan = "pro"
        else:
            # unknown price -> keep plan but store ids for manual debugging
            log.warning("Stripe price id not mapped to plan: %s", price_id)

        await self.db.flush()

