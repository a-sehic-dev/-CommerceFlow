from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from email.message import EmailMessage
from typing import Deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.usage_tracking_service import UsageTrackingService
from app.utils.app_timezone import now_local

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger("commerceflow.assistant")

SYSTEM_PROMPT = """You are CommerceFlow Assistant.

CommerceFlow is an ecommerce operational intelligence platform built by Sedin Šehić.

The platform supports:
- CSV/XLSX imports
- inventory intelligence
- operational analytics
- KPI dashboards
- ecommerce exports
- reporting workflows
- alerts and recommendations
- Shopify/WooCommerce support

You help users:
- understand CommerceFlow as an operational analytics workflow
- upload/import sales, product, and inventory files
- interpret inventory risk, profit leakage, dashboards, KPI systems, alerts, and reports
- choose the next action in the workspace
- evaluate the temporary guest workspace without implying authentication exists

Response style:
- keep replies short: usually 2-5 bullets or 1 short paragraph plus bullets
- avoid long ChatGPT-style walls of text
- make guidance actionable and onboarding-friendly
- use an enterprise support tone
- prefer operational intelligence, analytics workflows, reporting infrastructure, inventory intelligence, and executive KPI systems language
- avoid sounding like a generic AI dashboard tool
Answer greetings naturally and vary phrasing.
If the user asks something unrelated, be helpful in one short sentence if appropriate, then gently guide back to CommerceFlow, ecommerce operations, analytics, imports, exports, dashboards, reports, inventory, alerts, workflows, or founder/product questions.
Do not sound like a generic chatbot. Do not repeatedly use the same canned response."""

WINDOW_SECONDS = 60 * 60
_session_events: dict[str, Deque[float]] = defaultdict(deque)
_ip_events: dict[str, Deque[float]] = defaultdict(deque)
_last_request_at: dict[str, float] = {}
_abuse_alerted: dict[str, float] = {}
_response_cache: dict[str, tuple[float, str]] = {}


class AssistantMessage(BaseModel):
    role: str
    text: str = Field(..., max_length=1200)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1200)
    session_id: str = Field(..., min_length=8, max_length=80)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=10)


class AssistantChatResponse(BaseModel):
    reply: str
    configured: bool = True
    fallback: bool = False
    remaining: int = 0
    support_email: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _trim(events: Deque[float], now: float) -> None:
    while events and now - events[0] > WINDOW_SECONDS:
        events.popleft()


def _cache_key(message: str) -> str | None:
    normalized = " ".join(message.lower().split())
    if len(normalized) > 180:
        return None
    return normalized


def _get_cached_reply(message: str) -> str | None:
    key = _cache_key(message)
    if not key:
        return None
    cached = _response_cache.get(key)
    if not cached:
        return None
    ts, reply = cached
    if time.time() - ts > 15 * 60:
        _response_cache.pop(key, None)
        return None
    return reply


def _set_cached_reply(message: str, reply: str) -> None:
    key = _cache_key(message)
    if not key:
        return
    if len(_response_cache) > 100:
        _response_cache.clear()
    _response_cache[key] = (time.time(), reply)


def _send_abuse_alert(identity: str, count: int, limit: int, ip: str, session_id: str) -> None:
    settings = get_settings()
    now = time.time()
    if now - _abuse_alerted.get(identity, 0) < WINDOW_SECONDS:
        return
    _abuse_alerted[identity] = now

    if not settings.smtp_host:
        logger.warning(
            "Assistant abuse detected but SMTP is not configured: identity=%s count=%s limit=%s ip=%s session=%s",
            identity,
            count,
            limit,
            ip,
            session_id,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "CommerceFlow assistant abuse alert"
    msg["From"] = settings.smtp_from_email or settings.smtp_username or settings.assistant_alert_email
    msg["To"] = settings.assistant_alert_email
    msg.set_content(
        "\n".join(
            [
                "CommerceFlow assistant abuse threshold exceeded.",
                f"Timestamp: {now_local().isoformat()}",
                f"Identity: {identity}",
                f"Request count: {count}",
                f"Limit: {limit}",
                f"IP: {ip}",
                f"Session: {session_id}",
            ]
        )
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        logger.exception("Failed to send assistant abuse alert email")


def _enforce_limits(session_id: str, ip: str) -> int:
    settings = get_settings()
    now = time.time()
    last = _last_request_at.get(session_id, 0)
    if now - last < settings.assistant_cooldown_seconds:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {settings.assistant_cooldown_seconds:g} seconds before asking again.",
        )
    _last_request_at[session_id] = now

    session_events = _session_events[session_id]
    ip_events = _ip_events[ip]
    _trim(session_events, now)
    _trim(ip_events, now)

    if len(session_events) >= settings.assistant_session_limit:
        _send_abuse_alert(
            f"session:{session_id}",
            len(session_events) + 1,
            settings.assistant_session_limit,
            ip,
            session_id,
        )
        raise HTTPException(
            status_code=429,
            detail="Assistant session limit reached. Please contact support for direct assistance.",
        )

    if len(ip_events) >= settings.assistant_ip_limit:
        _send_abuse_alert(
            f"ip:{ip}",
            len(ip_events) + 1,
            settings.assistant_ip_limit,
            ip,
            session_id,
        )
        raise HTTPException(
            status_code=429,
            detail="Assistant request limit reached from this network. Please contact support for direct assistance.",
        )

    session_events.append(now)
    ip_events.append(now)
    return max(settings.assistant_session_limit - len(session_events), 0)


def _call_openai(message: str, history: list[AssistantMessage]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    recent_messages = []
    for item in history[-8:]:
        role = "assistant" if item.role == "assistant" else "user"
        text = item.text.strip()
        if text:
            recent_messages.append({"role": role, "content": text[:1200]})

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *recent_messages,
            {"role": "user", "content": message},
        ],
        "temperature": 0.35,
        "max_tokens": 320,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("OpenAI assistant request failed: %s", body)
        raise RuntimeError("Assistant provider request failed") from exc

    content = data["choices"][0]["message"]["content"].strip()
    return content or "I could not generate a useful CommerceFlow response."


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    body: AssistantChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    ip = _client_ip(request)
    remaining = _enforce_limits(body.session_id, ip)
    message = body.message.strip()

    if not settings.openai_api_key:
        return AssistantChatResponse(
            reply=(
                "- Assistant is available, but `OPENAI_API_KEY` is not configured yet.\n"
                "- You can still use imports, dashboards, reports, and analysis workflows.\n"
                "- For direct support: commerceflow.platform@gmail.com"
            ),
            configured=False,
            fallback=True,
            remaining=remaining,
            support_email=settings.assistant_alert_email,
        )

    try:
        cached = _get_cached_reply(message)
        if cached:
            reply = cached
        else:
            reply = await asyncio.to_thread(_call_openai, message, body.history)
            _set_cached_reply(message, reply)
    except Exception:
        logger.exception("CommerceFlow assistant failed")
        return AssistantChatResponse(
            reply=(
                "- I could not complete this assistant request right now.\n"
                "- Try again in a moment or continue with the workspace workflow.\n"
                "- Support: commerceflow.platform@gmail.com"
            ),
            fallback=True,
            remaining=remaining,
            support_email=settings.assistant_alert_email,
        )

    await UsageTrackingService(db).record(
        event_type="assistant_chat",
        path="/",
        session_id=body.session_id,
        meta={"configured": True},
    )
    return AssistantChatResponse(
        reply=reply,
        remaining=remaining,
        support_email=settings.assistant_alert_email,
    )
