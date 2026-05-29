"""Pre-load guest watch demo so visitors never upload files manually."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.active_dataset_service import ActiveDatasetService
from app.services.demo_loader_service import (
    WATCH_DEMO_FILES,
    DemoLoaderService,
    discover_demo_companies,
)

logger = logging.getLogger("commerceflow.demo_bootstrap")

_bootstrap_lock = asyncio.Lock()
_bootstrap_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "company": None,
}


def get_bootstrap_state() -> dict[str, Any]:
    return dict(_bootstrap_state)


def should_auto_bootstrap() -> bool:
    settings = get_settings()
    return settings.auto_bootstrap_demo and settings.workspace_mode == "demo_workspace"


async def watch_workspace_ready(session: AsyncSession) -> bool:
    loader = DemoLoaderService(session)
    ids: dict[str, int] = {}
    for dtype, filename in WATCH_DEMO_FILES.items():
        record = await loader._existing_completed_import(filename)
        if not record:
            return False
        ids[dtype] = record.id

    active = await ActiveDatasetService(session).get_active()
    return (
        active.products_import_id == ids["products"]
        and active.sales_import_id == ids["sales"]
        and active.inventory_import_id == ids["inventory"]
    )


async def bootstrap_watch_if_needed(session: AsyncSession, *, force: bool = False) -> dict:
    if not should_auto_bootstrap():
        return {"ready": False, "skipped": True, "message": "Auto bootstrap disabled"}

    if not discover_demo_companies():
        return {"ready": False, "skipped": True, "message": "Sample workspace files missing on server"}

    if not force and await watch_workspace_ready(session):
        return {
            "ready": True,
            "skipped": True,
            "message": "Sample workspace already loaded",
            "company": "watch",
        }

    active = await ActiveDatasetService(session).get_active()
    if not force and active.has_selection and not await watch_workspace_ready(session):
        return {
            "ready": False,
            "skipped": True,
            "message": "Operational datasets already selected — sample bootstrap skipped",
        }

    loader = DemoLoaderService(session)
    result = await loader.load_company("watch", fresh=False)
    return {
        "ready": True,
        "skipped": False,
        "message": result.get("message") or "Sample workspace loaded",
        "company": result.get("company", "watch"),
        "import_ids": result.get("import_ids"),
    }


# Backward-compatible aliases
bootstrap_atlas_if_needed = bootstrap_watch_if_needed
atlas_workspace_ready = watch_workspace_ready


async def run_startup_demo_bootstrap() -> None:
    if not should_auto_bootstrap():
        return

    from app.database import async_session_factory

    async with _bootstrap_lock:
        if _bootstrap_state["status"] == "running":
            return
        _bootstrap_state["status"] = "running"
        _bootstrap_state["message"] = "Loading ChronoHaus Watch Co. sample datasets…"

    try:
        async with async_session_factory() as session:
            if await watch_workspace_ready(session):
                _bootstrap_state["status"] = "ready"
                _bootstrap_state["message"] = "Sample workspace already loaded"
                _bootstrap_state["company"] = "watch"
                return
            result = await bootstrap_watch_if_needed(session)
            await session.commit()
        _bootstrap_state["status"] = "ready"
        _bootstrap_state["message"] = result.get("message", "")
        _bootstrap_state["company"] = result.get("company", "watch")
        logger.info("Demo bootstrap finished: %s", result)
    except Exception as exc:
        _bootstrap_state["status"] = "failed"
        _bootstrap_state["message"] = str(exc)
        logger.exception("Demo bootstrap failed")
