"""Pre-import watch sample into Import History; other packs load on demand."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.active_dataset_service import ActiveDatasetService
from app.services.demo_loader_service import DemoLoaderService, discover_demo_companies

logger = logging.getLogger("commerceflow.demo_bootstrap")

_bootstrap_lock = asyncio.Lock()
_bootstrap_state: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "company": "watch",
}


def get_bootstrap_state() -> dict[str, Any]:
    return dict(_bootstrap_state)


def should_auto_bootstrap() -> bool:
    settings = get_settings()
    return settings.auto_bootstrap_demo and settings.workspace_mode == "demo_workspace"


async def workspace_imports_ready(session: AsyncSession, key: str) -> bool:
    workspaces = discover_demo_companies()
    files = workspaces.get(key)
    if not files:
        return False
    loader = DemoLoaderService(session)
    for dtype in ("products", "inventory", "sales"):
        filename = files.get(dtype)
        if not filename or not await loader._existing_completed_import(filename):
            return False
    return True


async def watch_workspace_ready(session: AsyncSession) -> bool:
    return await workspace_imports_ready(session, "watch")


async def bootstrap_watch_if_needed(session: AsyncSession, *, force: bool = False) -> dict:
    """Import ChronoHaus watch pack into Import History only (no Run Analysis pre-selection)."""
    if not should_auto_bootstrap() and not force:
        return {"ready": False, "skipped": True, "message": "Auto bootstrap disabled"}

    workspaces = discover_demo_companies()
    if "watch" not in workspaces:
        return {"ready": False, "skipped": True, "message": "Watch sample files missing on server"}

    if not force and await watch_workspace_ready(session):
        return {
            "ready": True,
            "skipped": True,
            "message": "Watch sample datasets are already in Import History.",
            "company": "watch",
        }

    loader = DemoLoaderService(session)
    import_ids = await loader.import_workspace("watch")
    await ActiveDatasetService(session).set_active(None, None, None)

    return {
        "ready": True,
        "skipped": False,
        "message": "Watch sample is in Import History — use Run Your Analysis to pick datasets.",
        "company": "watch",
        "import_ids": import_ids,
        "available_workspaces": sorted(workspaces.keys()),
    }


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
        _bootstrap_state["message"] = "Importing watch sample into Import History…"

    try:
        async with async_session_factory() as session:
            result = await bootstrap_watch_if_needed(session)
            await session.commit()
        _bootstrap_state["status"] = "ready"
        _bootstrap_state["message"] = result.get("message", "")
        _bootstrap_state["company"] = result.get("company", "watch")
        logger.info("Watch demo bootstrap: %s", result)
    except Exception as exc:
        _bootstrap_state["status"] = "failed"
        _bootstrap_state["message"] = str(exc)
        logger.exception("Watch demo bootstrap failed")
