"""One-click demo company load: import packs, select datasets, run analysis."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.active_dataset_service import ActiveDatasetService
from app.services.analytics_orchestrator import AnalyticsOrchestrator
from app.services.import_service import ImportService
from app.services.reset_service import ResetService
from app.utils.cache import analytics_cache

logger = logging.getLogger("commerceflow.demo")

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "data" / "demo_companies"

DEMO_COMPANIES: dict[str, dict[str, str]] = {
    "nike": {
        "products": "products_nike_catalog.xlsx",
        "inventory": "inventory_nike_warehouse.xlsx",
        "sales": "sales_nike_q1_2025.xlsx",
    },
    "apple": {
        "products": "products_apple_catalog.xlsx",
        "inventory": "inventory_apple_warehouse.xlsx",
        "sales": "sales_apple_store_q1_2025.xlsx",
    },
    "zara": {
        "products": "products_zara_catalog.xlsx",
        "inventory": "inventory_zara_warehouse.xlsx",
        "sales": "sales_zara_global_q1_2025.xlsx",
    },
}


class DemoLoaderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.imports = ImportService(session)
        self.reset = ResetService(session)

    def ensure_demo_files(self) -> None:
        missing = [
            name
            for files in DEMO_COMPANIES.values()
            for name in files.values()
            if not (DEMO_DIR / name).is_file()
        ]
        if not missing:
            return
        script = ROOT / "scripts" / "generate_demo_datasets.py"
        logger.info("Generating missing demo files: %s", missing)
        subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )

    async def load_company(self, company: str, *, fresh: bool = True) -> dict:
        key = company.lower().strip()
        if key not in DEMO_COMPANIES:
            raise ValueError(f"Unknown demo company: {company}")

        self.ensure_demo_files()
        files = DEMO_COMPANIES[key]

        if fresh:
            await self.reset.reset_demo_environment()

        import_ids: dict[str, int] = {}
        for dtype in ("products", "inventory", "sales"):
            path = DEMO_DIR / files[dtype]
            if not path.is_file():
                raise FileNotFoundError(f"Demo file missing: {path}")
            record = await self.imports.create_import(path.name, "generic", dataset_type="auto")
            record = await self.imports.process_file(record.id, path, "generic")
            if record.status != "completed":
                raise RuntimeError(f"Import failed for {path.name}: {record.errors_json}")
            if record.needs_type_confirmation:
                raise RuntimeError(
                    f"Demo file {path.name} needs manual type confirmation — check column headers"
                )
            import_ids[dtype] = record.id

        active = await ActiveDatasetService(self.session).set_active(
            products_import_id=import_ids["products"],
            sales_import_id=import_ids["sales"],
            inventory_import_id=import_ids["inventory"],
        )
        analytics_cache.invalidate()

        selection = {
            "products_import_id": import_ids["products"],
            "sales_import_id": import_ids["sales"],
            "inventory_import_id": import_ids["inventory"],
        }
        orchestrator = AnalyticsOrchestrator(self.session)
        pipeline = await orchestrator.run_analysis_pipeline(
            use_cache=False,
            selection=selection,
            options={
                "rebuild_dashboard": True,
                "regenerate_alerts": True,
                "recalculate_inventory_risks": True,
                "export_report_after": False,
            },
        )

        label = key.capitalize()
        return {
            "success": pipeline.get("success", False),
            "message": f"{label} demo loaded and analysis complete",
            "company": key,
            "import_ids": import_ids,
            "active_datasets": active.model_dump(),
            "pipeline": {
                "success": pipeline.get("success"),
                "message": pipeline.get("message"),
                "stages": pipeline.get("stages", []),
            },
        }
