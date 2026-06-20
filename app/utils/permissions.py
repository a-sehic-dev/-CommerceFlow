"""Organization role checks for team workspaces."""

from __future__ import annotations

from fastapi import HTTPException

ROLE_OWNER = "owner"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

ROLE_RANK = {ROLE_VIEWER: 1, ROLE_ANALYST: 2, ROLE_OWNER: 3}


def normalize_role(role: str | None) -> str:
    value = (role or ROLE_ANALYST).strip().lower()
    if value not in ROLE_RANK:
        return ROLE_ANALYST
    return value


def require_role(user_role: str | None, minimum: str) -> None:
    current = normalize_role(user_role)
    if ROLE_RANK[current] < ROLE_RANK[minimum]:
        raise HTTPException(403, detail=f"This action requires {minimum} access.")
