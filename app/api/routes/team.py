from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.team import AcceptInviteRequest
from app.services.auth_service import AuthService
from app.services.plan_service import PlanService
from app.services.team_service import TeamService
from app.utils.permissions import ROLE_OWNER, require_role
from app.utils.session_auth import create_session_token, require_session, set_session_cookie

router = APIRouter(prefix="/api/team", tags=["team"])


class InviteRequest(BaseModel):
    email: str = Field(..., max_length=256)
    role: str = Field(default="analyst", max_length=32)


@router.get("/members")
async def list_members(request: Request, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    service = TeamService(db)
    limits = await PlanService(db).limits_payload(auth.organization_id)
    return {
        "members": await service.list_members(auth.organization_id),
        "pending_invites": await service.list_pending_invites(auth.organization_id),
        "seat_limit": await service.seat_limit(auth.organization_id),
        "seats_used": await service.seat_count(auth.organization_id),
        "plan": limits,
    }


@router.post("/invite")
async def invite_member(request: Request, body: InviteRequest, db: AsyncSession = Depends(get_db)):
    auth = require_session(request)
    user = await AuthService(db).get_user_by_id(auth.user_id)
    require_role(user.role if user else None, ROLE_OWNER)
    try:
        invite = await TeamService(db).create_invite(
            organization_id=auth.organization_id,
            email=body.email,
            role=body.role,
            invited_by_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return {
        "success": True,
        "email": invite.email,
        "role": invite.role,
        "expires_at": invite.expires_at.isoformat(),
    }


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await TeamService(db).accept_invite(
            token=body.invite_token,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    token = create_session_token(user.id, user.organization_id, user.email)
    set_session_cookie(response, token)
    await db.commit()
    return {
        "success": True,
        "email": user.email,
        "organization_id": user.organization_id,
        "role": user.role,
    }
