from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organization import Organization
from app.schemas.auth import AuthUserResponse, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.services.usage_tracking_service import UsageTrackingService
from app.utils.session_auth import (
    clear_session_cookie,
    create_session_token,
    get_session_from_request,
    require_session,
    set_session_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _user_response(session: AsyncSession, user_id: int, org_id: int, email: str) -> AuthUserResponse:
    org_name = await session.scalar(select(Organization.name).where(Organization.id == org_id))
    user = await AuthService(session).get_user_by_id(user_id)
    return AuthUserResponse(
        id=user_id,
        email=email,
        full_name=user.full_name if user else None,
        organization_id=org_id,
        organization_name=org_name,
    )


@router.post("/register", response_model=AuthUserResponse)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user = await service.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            company_name=body.company_name,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    token = create_session_token(user.id, user.organization_id, user.email)
    set_session_cookie(response, token)
    await UsageTrackingService(db).record(
        event_type="auth_register",
        path="/login",
        session_id=f"user-{user.id}",
        meta={
            "email": user.email,
            "organization_id": user.organization_id,
            "company_name": body.company_name.strip(),
        },
    )
    return await _user_response(db, user.id, user.organization_id, user.email)


@router.post("/login", response_model=AuthUserResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user = await service.authenticate(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(401, detail=str(exc)) from exc

    token = create_session_token(user.id, user.organization_id, user.email)
    set_session_cookie(response, token)
    await UsageTrackingService(db).record(
        event_type="auth_login",
        path="/login",
        session_id=f"user-{user.id}",
        meta={"email": user.email, "organization_id": user.organization_id},
    )
    return await _user_response(db, user.id, user.organization_id, user.email)


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"success": True}


@router.get("/me", response_model=AuthUserResponse)
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    return await _user_response(db, auth.user_id, auth.organization_id, auth.email)


@router.get("/session")
async def session_status(request: Request, db: AsyncSession = Depends(get_db)):
    auth = get_session_from_request(request)
    if not auth:
        return {"authenticated": False}
    payload = await _user_response(db, auth.user_id, auth.organization_id, auth.email)
    return {"authenticated": True, "user": payload.model_dump()}
