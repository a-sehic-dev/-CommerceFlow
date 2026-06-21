from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.auth_service import AuthService
from app.services.plan_service import PlanService
from app.services.stripe_service import StripeService
from app.services.team_service import TeamService
from app.utils.plan_limits import PLAN_LIMITS, plan_limits_payload
from app.utils.permissions import ROLE_OWNER, require_role
from app.utils.session_auth import require_session

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str = Field(..., min_length=2, max_length=16)  # pro | team | ultra


@router.get("/plans")
async def list_plans():
    return {"plans": [plan_limits_payload(slug) for slug in PLAN_LIMITS]}


@router.get("/status")
async def billing_status(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    org = await StripeService(db).get_org(auth.organization_id)
    plan_svc = PlanService(db)
    team_svc = TeamService(db)
    return {
        "plan": org.plan,
        "limits": await plan_svc.limits_payload(auth.organization_id),
        "usage": {
            "seats_used": await team_svc.seat_count(auth.organization_id),
            "stores_used": await plan_svc.connected_store_count(auth.organization_id),
        },
        "role": user.role if user else None,
        "stripe": {
            "customer_id": org.stripe_customer_id,
            "subscription_id": org.stripe_subscription_id,
            "subscription_status": org.stripe_subscription_status,
            "price_id": org.stripe_price_id,
        },
    }


@router.post("/checkout")
async def start_checkout(body: CheckoutRequest, request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_OWNER)

    settings = get_settings()
    service = StripeService(db)
    org = await service.get_org(auth.organization_id)

    plan = body.plan.strip().lower()
    price_map = {
        "pro": settings.stripe_price_pro,
        "team": settings.stripe_price_team,
        "ultra": settings.stripe_price_ultra,
    }
    if plan not in price_map:
        raise HTTPException(400, "Unknown plan. Use 'pro', 'team', or 'ultra'.")
    price_id = price_map[plan]

    if not price_id:
        raise HTTPException(503, "Stripe price id is not configured for this plan.")

    success = f"{settings.app_base_url}/dashboard?billing=success"
    cancel = f"{settings.app_base_url}/dashboard?billing=cancel"
    url = await service.create_checkout_session(org=org, price_id=price_id, success_url=success, cancel_url=cancel)
    return {"url": url}


@router.post("/portal")
async def open_portal(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_OWNER)

    settings = get_settings()
    service = StripeService(db)
    org = await service.get_org(auth.organization_id)
    url = await service.create_billing_portal_session(org=org, return_url=f"{settings.app_base_url}/dashboard?billing=portal")
    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Stripe webhook is not configured.")
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe secret key is not configured.")
    stripe.api_key = settings.stripe_secret_key

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig, secret=settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(400, "Invalid webhook signature.") from exc

    evt_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    # We accept both subscription created/updated; checkout completion is the fastest path.
    if evt_type in {"customer.subscription.created", "customer.subscription.updated"}:
        org_id = None
        metadata = obj.get("metadata") or {}
        if metadata.get("organization_id"):
            try:
                org_id = int(metadata["organization_id"])
            except ValueError:
                org_id = None

        if not org_id:
            # fallback: if customer has metadata
            customer_id = obj.get("customer")
            if customer_id:
                customer = stripe.Customer.retrieve(customer_id)
                md = (customer.get("metadata") or {}) if isinstance(customer, dict) else {}
                if md.get("organization_id"):
                    try:
                        org_id = int(md["organization_id"])
                    except ValueError:
                        org_id = None

        if org_id:
            await StripeService(db).apply_subscription_from_stripe(organization_id=org_id, subscription=obj)
            await db.commit()

    if evt_type == "checkout.session.completed":
        # if it's a subscription checkout, update using the subscription object
        org_id = None
        md = obj.get("metadata") or {}
        if md.get("organization_id"):
            try:
                org_id = int(md["organization_id"])
            except ValueError:
                org_id = None

        sub_id = obj.get("subscription")
        if org_id and sub_id:
            subscription = stripe.Subscription.retrieve(sub_id)
            await StripeService(db).apply_subscription_from_stripe(organization_id=org_id, subscription=subscription)
            await db.commit()

    return {"received": True, "type": evt_type}

