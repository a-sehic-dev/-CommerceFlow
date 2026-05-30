"""One-click evaluation workspace load: import packs and stage datasets for analysis."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import import_status as ST
from app.models.import_record import ImportRecord
from app.services.active_dataset_service import ActiveDatasetService
from app.services.import_service import ImportService
from app.services.reset_service import ResetService
from app.utils.cache import analytics_cache

logger = logging.getLogger("commerceflow.demo")

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "data" / "demo_companies"

DEMO_DATASET_TYPES = ("products", "inventory", "sales")
# Guest / portfolio demo: ChronoHaus Watch Co. (medium-size, fast on Render).
DEMO_WORKSPACE_KEYS = frozenset({"watch", "auto"})
WATCH_DEMO_FILES = {
    "products": "watch_products.xlsx",
    "inventory": "watch_inventory.xlsx",
    "sales": "watch_sales_2025.xlsx",
}


def _dataset_type_from_name(path: Path) -> str | None:
    name = path.name.lower()
    if not name.endswith(".xlsx"):
        return None
    if re.search(r"(^|_)sales(_|\.|$)", name):
        return "sales"
    if re.search(r"(^|_)products(_|\.|$)", name):
        return "products"
    if re.search(r"(^|_)inventory(_|\.|$)", name):
        return "inventory"
    return None


def _workspace_key_from_name(path: Path, dtype: str) -> str | None:
    stem = path.stem.lower()
    marker = f"_{dtype}"
    if marker in stem:
        key = stem.split(marker, 1)[0]
    else:
        key = stem.rsplit(dtype, 1)[0].strip("_- ")
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key or None


def discover_demo_companies() -> dict[str, dict[str, str]]:
    """Build complete evaluation workspaces from current files on disk."""
    workspaces: dict[str, dict[str, str]] = {}
    if not DEMO_DIR.is_dir():
        logger.info("Demo directory not found: %s", DEMO_DIR)
        return workspaces

    for path in sorted(DEMO_DIR.glob("*.xlsx")):
        dtype = _dataset_type_from_name(path)
        if not dtype:
            logger.info("Skipping unclassified evaluation dataset: %s", path.name)
            continue
        key = _workspace_key_from_name(path, dtype)
        if not key:
            logger.info("Skipping evaluation dataset without workspace key: %s", path.name)
            continue
        workspaces.setdefault(key, {})[dtype] = path.name

    complete = {
        key: files
        for key, files in workspaces.items()
        if key in DEMO_WORKSPACE_KEYS and all(dtype in files for dtype in DEMO_DATASET_TYPES)
    }
    skipped = sorted(set(workspaces) - set(complete))
    if skipped:
        logger.info("Skipping incomplete evaluation workspaces: %s", ", ".join(skipped))
    return complete


def get_demo_companies() -> dict[str, dict[str, str]]:
    return discover_demo_companies()


class DemoLoaderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.imports = ImportService(session)
        self.reset = ResetService(session)

    def ensure_demo_files(self) -> None:
        if not discover_demo_companies():
            logger.warning("No complete evaluation workspace found in %s", DEMO_DIR)

    async def _existing_completed_import(self, filename: str) -> ImportRecord | None:
        result = await self.session.execute(
            select(ImportRecord)
            .where(ImportRecord.filename == filename, ImportRecord.status == ST.COMPLETED)
            .order_by(ImportRecord.started_at.desc(), ImportRecord.id.desc())
        )
        return result.scalars().first()

    async def _ensure_import(self, filename: str) -> ImportRecord | None:
        path = DEMO_DIR / filename
        if not path.is_file():
            logger.warning("Skipping missing evaluation dataset: %s", path)
            return None
        record = await self._existing_completed_import(path.name)
        if record is None:
            record = await self.imports.create_import(path.name, "generic", dataset_type="auto")
            record = await self.imports.process_file(record.id, path, "generic")
        if record.status != "completed":
            logger.warning("Skipping failed sample import %s: %s", path.name, record.errors_json)
            return None
        if record.needs_type_confirmation:
            logger.warning(
                "Skipping sample import that needs type confirmation: %s", path.name
            )
            return None
        return record

    async def ensure_all_demo_imports(self) -> dict[str, dict[str, int]]:
        """Import every demo company pack into history without removing existing imports."""
        import_ids: dict[str, dict[str, int]] = {}
        for key, files in discover_demo_companies().items():
            workspace_ids: dict[str, int] = {}
            for dtype in DEMO_DATASET_TYPES:
                filename = files.get(dtype)
                if not filename:
                    continue
                record = await self._ensure_import(filename)
                if record:
                    workspace_ids[dtype] = record.id
            if workspace_ids:
                import_ids[key] = workspace_ids
        return import_ids

    def _resolve_workspace_key(self, company: str, workspaces: dict[str, dict[str, str]]) -> str:
        key = company.lower().strip()
        if key in ("sandbox", "demo", "guest"):
            if "watch" in workspaces:
                return "watch"
        if key == "atlas" and "watch" in workspaces:
            return "watch"
        if key in ("auto", "car", "cars", "parts"):
            if "auto" in workspaces:
                return "auto"
        if key in workspaces:
            return key
        if not workspaces:
            raise FileNotFoundError("Evaluation workspace is temporarily unavailable.")
        logger.info("Requested evaluation workspace %s not found; using first available workspace", key)
        return sorted(workspaces)[0]

    async def load_company(self, company: str, *, fresh: bool = True) -> dict:
        workspaces = discover_demo_companies()
        if not workspaces:
            raise FileNotFoundError("Evaluation workspace is temporarily unavailable.")

        self.ensure_demo_files()

        if fresh:
            await self.reset.reset_demo_environment()

        all_imports = await self.ensure_all_demo_imports()
        key = self._resolve_workspace_key(company, workspaces)
        import_ids = all_imports.get(key)
        if not import_ids:
            files = workspaces[key]
            import_ids = {}
            for dtype in DEMO_DATASET_TYPES:
                record = await self._ensure_import(files[dtype])
                if record:
                    import_ids[dtype] = record.id

        missing_types = [dtype for dtype in DEMO_DATASET_TYPES if dtype not in import_ids]
        if missing_types:
            logger.warning("Sample workspace %s incomplete, missing: %s", key, ", ".join(missing_types))
            raise FileNotFoundError("Sample workspace is temporarily unavailable.")

        active = await ActiveDatasetService(self.session).set_active(
            products_import_id=import_ids["products"],
            sales_import_id=import_ids["sales"],
            inventory_import_id=import_ids["inventory"],
        )
        analytics_cache.invalidate()

        return {
            "success": True,
            "message": "Sample workspace is loaded — click Run Your Analysis to view KPIs and charts.",
            "company": key,
            "import_ids": import_ids,
            "available_workspaces": sorted(all_imports.keys()),
            "active_datasets": active.model_dump(),
            "requires_analysis_generation": True,
        }
