"""Team invites and member management."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.organization import Organization
from app.models.team_invite import TeamInvite
from app.models.user import User
from app.services.auth_service import validate_email
from app.utils.app_timezone import naive_local_now
from app.utils.founder_email import send_email
from app.utils.permissions import ROLE_ANALYST, ROLE_OWNER, normalize_role


class TeamService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def seat_count(self, organization_id: int) -> int:
        members = await self.session.scalar(
            select(func.count()).select_from(User).where(
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
        )
        pending = await self.session.scalar(
            select(func.count()).select_from(TeamInvite).where(
                TeamInvite.organization_id == organization_id,
                TeamInvite.accepted_at.is_(None),
                TeamInvite.expires_at > naive_local_now(),
            )
        )
        return int(members or 0) + int(pending or 0)

    async def list_members(self, organization_id: int) -> list[dict]:
        result = await self.session.execute(
            select(User).where(User.organization_id == organization_id, User.is_active.is_(True))
        )
        return [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": normalize_role(u.role),
            }
            for u in result.scalars().all()
        ]

    async def list_pending_invites(self, organization_id: int) -> list[dict]:
        result = await self.session.execute(
            select(TeamInvite)
            .where(
                TeamInvite.organization_id == organization_id,
                TeamInvite.accepted_at.is_(None),
                TeamInvite.expires_at > naive_local_now(),
            )
            .order_by(TeamInvite.created_at.desc())
        )
        return [
            {
                "id": inv.id,
                "email": inv.email,
                "role": normalize_role(inv.role),
                "expires_at": inv.expires_at.isoformat(),
            }
            for inv in result.scalars().all()
        ]

    async def create_invite(
        self,
        *,
        organization_id: int,
        email: str,
        role: str,
        invited_by_user_id: int,
    ) -> TeamInvite:
        email_norm = validate_email(email)
        role_norm = normalize_role(role)
        if role_norm == ROLE_OWNER:
            raise ValueError("Cannot invite another owner. Transfer ownership is not automated yet.")

        if await self.seat_count(organization_id) >= self.settings.team_max_seats:
            raise ValueError(f"Seat limit reached ({self.settings.team_max_seats} per organization).")

        existing_user = await self.session.scalar(
            select(User).where(User.email == email_norm, User.organization_id == organization_id)
        )
        if existing_user:
            raise ValueError("This person is already in your workspace.")

        pending = await self.session.scalar(
            select(TeamInvite.id).where(
                TeamInvite.organization_id == organization_id,
                TeamInvite.email == email_norm,
                TeamInvite.accepted_at.is_(None),
                TeamInvite.expires_at > naive_local_now(),
            )
        )
        if pending:
            raise ValueError("An invite is already pending for this email.")

        token = secrets.token_urlsafe(32)
        invite = TeamInvite(
            organization_id=organization_id,
            email=email_norm,
            role=role_norm,
            token=token,
            invited_by_user_id=invited_by_user_id,
            expires_at=naive_local_now()
            + timedelta(hours=self.settings.invite_token_ttl_hours),
        )
        self.session.add(invite)
        await self.session.flush()

        org_name = await self.session.scalar(
            select(Organization.name).where(Organization.id == organization_id)
        )
        accept_url = f"{self.settings.app_base_url.rstrip('/')}/login?invite={token}"
        send_email(
            to=email_norm,
            subject=f"Join {org_name or 'CommerceFlow'} workspace",
            body=(
                f"You were invited to join {org_name or 'a CommerceFlow workspace'} as {role_norm}.\n\n"
                f"Accept invite: {accept_url}\n\n"
                f"This link expires in {self.settings.invite_token_ttl_hours} hours."
            ),
        )
        return invite

    async def accept_invite(
        self,
        *,
        token: str,
        email: str,
        password: str,
        full_name: str | None,
    ) -> User:
        from app.services.auth_service import AuthService, validate_password, hash_password

        email_norm = validate_email(email)
        validate_password(password)
        invite = await self.session.scalar(
            select(TeamInvite).where(TeamInvite.token == token.strip())
        )
        if not invite or invite.accepted_at:
            raise ValueError("Invite link is invalid or already used.")
        if invite.expires_at < naive_local_now():
            raise ValueError("Invite link has expired.")
        if invite.email != email_norm:
            raise ValueError("Use the same email address that received the invite.")

        existing = await AuthService(self.session).get_user_by_email(email_norm)
        if existing:
            if existing.organization_id == invite.organization_id:
                raise ValueError("You already belong to this workspace.")
            raise ValueError("This email already has a CommerceFlow account.")

        user = User(
            email=email_norm,
            full_name=(full_name or "").strip() or None,
            hashed_password=hash_password(password),
            organization_id=invite.organization_id,
            role=normalize_role(invite.role),
            is_active=True,
        )
        self.session.add(user)
        invite.accepted_at = naive_local_now()
        await self.session.flush()
        return user
