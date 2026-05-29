"""Server-side usage events — reliable on Render (client fetch can fail silently)."""

from __future__ import annotations

import asyncio
import logging
import uuid

from starlette.requests import Request
from starlette.responses import Response

from app.database import async_session_factory
from app.services.usage_tracking_service import UsageTrackingService

logger = logging.getLogger("commerceflow.usage")

SESSION_COOKIE = "cf_guest_session"

# GET HTML routes to track (path -> event_type)
TRACKABLE_PAGES: dict[str, str] = {
    "/": "landing_view",
    "/dashboard": "page_view",
    "/products": "page_view",
    "/inventory": "page_view",
    "/profit": "page_view",
    "/alerts": "page_view",
    "/imports": "page_view",
    "/reports": "page_view",
    "/guide": "page_view",
}


async def _persist_event(event_type: str, path: str, session_id: str | None) -> None:
    try:
        async with async_session_factory() as session:
            await UsageTrackingService(session).record(
                event_type=event_type,
                path=path,
                session_id=session_id,
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record usage event %s %s", event_type, path)


async def usage_page_middleware(request: Request, call_next) -> Response:
    event_type = TRACKABLE_PAGES.get(request.url.path)
    run_track = request.method == "GET" and event_type is not None

    session_id = request.cookies.get(SESSION_COOKIE)
    if run_track and not session_id:
        session_id = str(uuid.uuid4())

    response = await call_next(request)

    if not run_track or response.status_code != 200:
        return response

    if not session_id:
        session_id = request.cookies.get(SESSION_COOKIE) or str(uuid.uuid4())

    media = (response.headers.get("content-type") or "").lower()
    if "text/html" not in media and event_type != "landing_view":
        return response

    if not request.cookies.get(SESSION_COOKIE):
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
            path="/",
        )

    asyncio.create_task(_persist_event(event_type, request.url.path, session_id))
    return response
