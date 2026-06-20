"""Registration and login for private organization workspaces."""

from __future__ import annotations

import re

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.utils.session_auth import slugify

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")


def hash_password(password: str) -> str:
    secret = _password_bytes(password)
    return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_password_bytes(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(_password_bytes(password)) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password must be 72 characters or fewer.")


async def _unique_org_slug(session: AsyncSession, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    n = 2
    while True:
        exists = await session.scalar(select(Organization.id).where(Organization.slug == candidate))
        if not exists:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        company_name: str,
    ) -> User:
        email_norm = validate_email(email)
        validate_password(password)
        company = (company_name or "").strip()
        if len(company) < 2:
            raise ValueError("Company name is required.")

        existing = await self.get_user_by_email(email_norm)
        if existing:
            raise ValueError("An account with this email already exists.")

        org = Organization(
            name=company,
            slug=await _unique_org_slug(self.session, company),
            plan="starter",
        )
        self.session.add(org)
        await self.session.flush()

        user = User(
            email=email_norm,
            full_name=(full_name or "").strip() or None,
            hashed_password=hash_password(password),
            organization_id=org.id,
            role="owner",
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        email_norm = validate_email(email)
        user = await self.get_user_by_email(email_norm)
        if not user or not user.is_active:
            raise ValueError("Invalid email or password.")
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password.")
        if not user.organization_id:
            raise ValueError("Account is missing an organization workspace.")
        return user
