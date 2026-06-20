"""Signed short-lived OAuth state tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import get_settings


def create_oauth_state(*, organization_id: int, user_id: int, ttl_seconds: int = 600) -> str:
    settings = get_settings()
    payload = {
        "oid": organization_id,
        "uid": user_id,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(settings.secret_key.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def parse_oauth_state(token: str) -> tuple[int, int]:
    if "." not in token:
        raise ValueError("Invalid OAuth state.")
    payload_b64, sig = token.rsplit(".", 1)
    settings = get_settings()
    expected = hmac.new(settings.secret_key.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Invalid OAuth state signature.")
    raw = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
    if int(raw.get("exp") or 0) < int(time.time()):
        raise ValueError("OAuth state expired. Start connect again.")
    return int(raw["oid"]), int(raw["uid"])
