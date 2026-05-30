"""Guest sample packs on disk — no auto-import into Run Your Analysis selection."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.demo_loader_service import DemoLoaderService, discover_demo_companies

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


async def workspace_imports_ready(session: AsyncSession, key: str) -> bool:
    """True when all three sample files for a workspace exist as completed imports."""
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
    """Do not import or pre-select datasets — only confirm sample files exist on server."""
    del force, session  # explicit load via /api/admin/demo/load/{company}
    workspaces = discover_demo_companies()
    if not workspaces:
        return {"ready": False, "skipped": True, "message": "Sample workspace files missing on server"}
    return {
        "ready": True,
        "skipped": True,
        "message": "Use Load Sample (Watches or Motor parts), then choose datasets in Run Your Analysis.",
        "available_workspaces": sorted(workspaces.keys()),
    }


# Backward-compatible aliases
bootstrap_atlas_if_needed = bootstrap_watch_if_needed
atlas_workspace_ready = watch_workspace_ready


async def run_startup_demo_bootstrap() -> None:
    if not should_auto_bootstrap():
        return

    async with _bootstrap_lock:
        if _bootstrap_state["status"] == "running":
            return
        _bootstrap_state["status"] = "ready"
        _bootstrap_state["message"] = (
            "Sample packs on server — load Watches or Motor parts, then pick imports in Run Your Analysis."
        )
        _bootstrap_state["company"] = None
    logger.info("Demo bootstrap skipped (no auto-import): %s", discover_demo_companies().keys())
