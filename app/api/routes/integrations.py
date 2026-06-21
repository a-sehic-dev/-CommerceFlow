from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.plan_service import PlanService
from app.services.store_connection_service import StoreConnectionService
from app.services.shopify_service import ShopifyService, normalize_shop_domain
from app.services.woocommerce_service import WooCommerceService, normalize_store_url
from app.utils.oauth_state import create_oauth_state, parse_oauth_state
from app.utils.permissions import ROLE_ANALYST, require_role
from app.utils.session_auth import require_session

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class WooConnectRequest(BaseModel):
    store_url: str = Field(..., min_length=4, max_length=512)
    consumer_key: str = Field(..., min_length=8, max_length=256)
    consumer_secret: str = Field(..., min_length=8, max_length=256)


@router.get("/status")
async def integration_status(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    plan_svc = PlanService(db)
    limits = await plan_svc.limits_payload(auth.organization_id)
    shopify_conns = await ShopifyService(db).list_connections(auth.organization_id)
    woo_conns = await WooCommerceService(db).list_connections(auth.organization_id)
    stores_used = await plan_svc.connected_store_count(auth.organization_id)
    return {
        "plan": limits,
        "stores_used": stores_used,
        "stores_limit": limits["max_stores"],
        "shopify": {
            "connected": bool(shopify_conns),
            "stores": [
                {
                    "store": c.store_domain,
                    "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
                }
                for c in shopify_conns
            ],
        },
        "woocommerce": {
            "connected": bool(woo_conns),
            "stores": [
                {
                    "store": c.store_domain,
                    "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
                }
                for c in woo_conns
            ],
        },
    }


@router.get("/shopify/install")
async def shopify_install(
    request: Request,
    shop: str = Query(..., min_length=3),
    db: AsyncSession = Depends(get_db),
):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_ANALYST)
    domain = normalize_shop_domain(shop)
    stores = StoreConnectionService(db)
    if not await stores.get_by_domain(auth.organization_id, "shopify", domain):
        await PlanService(db).ensure_can_add_store(auth.organization_id)
    state = create_oauth_state(organization_id=auth.organization_id, user_id=auth.user_id)
    url = ShopifyService(db).authorize_url(shop, state)
    return {"authorize_url": url}


@router.get("/shopify/callback")
async def shopify_callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    params = {k: v for k, v in request.query_params.items()}
    service = ShopifyService(db)
    if not service.verify_hmac(params):
        raise HTTPException(400, "Invalid Shopify callback signature.")
    org_id, user_id = parse_oauth_state(state)
    token = await service.exchange_token(shop, code)
    await service.save_connection(org_id, shop, token)
    await db.commit()
    return RedirectResponse(url="/imports?shopify=connected")


@router.post("/shopify/sync")
async def shopify_sync(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_ANALYST)
    try:
        result = await ShopifyService(db).sync_store(auth.organization_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return {"success": True, **result}


@router.post("/woocommerce/connect")
async def woocommerce_connect(
    request: Request,
    body: WooConnectRequest,
    db: AsyncSession = Depends(get_db),
):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_ANALYST)
    base = normalize_store_url(body.store_url)
    stores = StoreConnectionService(db)
    if not await stores.get_by_domain(auth.organization_id, "woocommerce", base):
        await PlanService(db).ensure_can_add_store(auth.organization_id)
    try:
        conn = await WooCommerceService(db).connect(
            auth.organization_id,
            body.store_url,
            body.consumer_key,
            body.consumer_secret,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return {
        "success": True,
        "store": conn.store_domain,
        "provider": "woocommerce",
    }


@router.post("/woocommerce/sync")
async def woocommerce_sync(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_ANALYST)
    try:
        result = await WooCommerceService(db).sync_store(auth.organization_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return {"success": True, **result}
