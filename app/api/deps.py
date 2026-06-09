"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.utils.session_auth import AuthSession, get_session_from_request


def get_optional_auth(request: Request) -> AuthSession | None:
    return get_session_from_request(request)


def get_organization_scope(request: Request) -> int | None:
    """Logged-in users see their org; guests see shared demo workspace (NULL org)."""
    auth = get_session_from_request(request)
    return auth.organization_id if auth else None
