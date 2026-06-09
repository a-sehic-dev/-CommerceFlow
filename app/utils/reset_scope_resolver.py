"""Resolve clear/reset scope from session cookie or founder key."""

from __future__ import annotations

from fastapi import Request

from app.config import get_settings
from app.services.reset_scope import ResetScope
from app.utils.session_auth import get_session_from_request


def resolve_reset_scope(request: Request, key: str | None = None) -> ResetScope:
    """
    Logged-in user → their organization only.
    Guest → guest imports (organization_id IS NULL) only.
    ?key=USAGE_STATS_KEY → founder global wipe (all tenants + guest).
    """
    settings = get_settings()
    expected = (settings.usage_stats_key or "").strip()
    if key and expected and key == expected:
        return ResetScope(global_all=True)

    auth = get_session_from_request(request)
    if auth:
        return ResetScope(organization_id=auth.organization_id)
    return ResetScope(organization_id=None)
