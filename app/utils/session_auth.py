"""Signed session cookie helpers for authenticated workspaces."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from app.config import get_settings

SESSION_COOKIE = "cf_auth"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@dataclass(frozen=True)
class AuthSession:
    user_id: int
    organization_id: int
    email: str


def _sign(payload_b64: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()


def create_session_token(user_id: int, organization_id: int, email: str) -> str:
    settings = get_settings()
    payload = {
        "uid": user_id,
        "oid": organization_id,
        "email": email,
        "exp": int(time.time()) + SESSION_MAX_AGE,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return f"{payload_b64}.{_sign(payload_b64, settings.secret_key)}"


def parse_session_token(token: str | None) -> AuthSession | None:
    if not token or "." not in token:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    settings = get_settings()
    if not hmac.compare_digest(_sign(payload_b64, settings.secret_key), sig):
        return None
    try:
        raw = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
    except (json.JSONDecodeError, ValueError):
        return None
    if int(raw.get("exp") or 0) < int(time.time()):
        return None
    uid = int(raw.get("uid") or 0)
    oid = int(raw.get("oid") or 0)
    email = str(raw.get("email") or "")
    if uid <= 0 or oid <= 0 or not email:
        return None
    return AuthSession(user_id=uid, organization_id=oid, email=email)


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    secure = settings.app_env == "production" and not settings.debug
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_session_from_request(request: Request) -> AuthSession | None:
    return parse_session_token(request.cookies.get(SESSION_COOKIE))


def require_session(request: Request) -> AuthSession:
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(401, detail="Sign in required.")
    return session


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:120] or "workspace"
