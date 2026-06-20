from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import AuthService
from app.services.shopify_service import ShopifyService
from app.services.woocommerce_service import WooCommerceService
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
    shopify = await ShopifyService(db).get_connection(auth.organization_id)
    woo = await WooCommerceService(db).get_connection(auth.organization_id)
    return {
        "shopify": {
            "connected": bool(shopify and shopify.status == "connected"),
            "store": shopify.store_domain if shopify else None,
            "last_sync_at": shopify.last_sync_at.isoformat() if shopify and shopify.last_sync_at else None,
        },
        "woocommerce": {
            "connected": bool(woo and woo.status == "connected"),
            "store": woo.store_domain if woo else None,
            "last_sync_at": woo.last_sync_at.isoformat() if woo and woo.last_sync_at else None,
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
