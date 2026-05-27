#!/usr/bin/env python3
"""Atlas-only demo: purge legacy imports, load data, analyze, sync landing preview."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_directories  # noqa: E402
from app.database import async_session_factory, init_db  # noqa: E402
from app.services.active_dataset_service import ActiveDatasetService  # noqa: E402
from app.services.analytics_orchestrator import AnalyticsOrchestrator  # noqa: E402
from app.services.import_service import ImportService  # noqa: E402
from app.utils.cache import analytics_cache  # noqa: E402

DEMO_DIR = ROOT / "data" / "demo_companies"
ATLAS_FILES = {
    "atlas_products.xlsx": "products",
    "atlas_inventory.xlsx": "inventory",
    "atlas_sales_q1_2026.xlsx": "sales",
}


async def _purge_atlas_imports(session) -> None:
    from sqlalchemy import delete, select
    from app.models.import_record import ImportRecord
    from app.models.inventory import InventoryRecord
    from app.models.product import Product
    from app.models.sales import SalesRecord

    result = await session.execute(
        select(ImportRecord).where(ImportRecord.filename.in_(tuple(ATLAS_FILES.keys())))
    )
    records = list(result.scalars().all())
    if not records:
        return
    ids = [r.id for r in records]
    await session.execute(delete(SalesRecord).where(SalesRecord.import_id.in_(ids)))
    await session.execute(delete(InventoryRecord).where(InventoryRecord.import_id.in_(ids)))
    await session.execute(delete(Product).where(Product.import_id.in_(ids)))
    await session.execute(delete(ImportRecord).where(ImportRecord.id.in_(ids)))
    await session.commit()
    print(f"  purged {len(ids)} prior Atlas import(s) for fresh reload")


async def _import_atlas(session, *, fresh: bool = True) -> dict[str, int]:
    service = ImportService(session)
    ids: dict[str, int] = {}
    if fresh:
        await _purge_atlas_imports(session)
    for filename, dtype in ATLAS_FILES.items():
        path = DEMO_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        record = await service.create_import(filename, "generic", dataset_type="auto")
        record = await service.process_file(record.id, path, "generic")
        if record.status != "completed":
            raise RuntimeError(f"Import failed for {filename}: {record.errors_json}")
        ids[dtype] = record.id
        print(f"  OK {filename} -> import #{record.id} ({record.success_count:,} rows)")
    return ids


async def main() -> None:
    ensure_directories()
    t0 = time.perf_counter()

    print("1/5 Purging legacy Nike/Apple/Zara imports...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "cleanup_demo_workspaces.py")], check=True, cwd=str(ROOT))

    snapshot_path = DEMO_DIR / "atlas_analytics_snapshot.json"
    if not snapshot_path.is_file():
        print("2/5 Generating Atlas datasets + preview snapshot...")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_atlas_demo.py")], check=True, cwd=str(ROOT))
    else:
        print("2/5 Atlas XLSX files present (skip generation)")

    await init_db()
    analytics_cache.invalidate()

    import_ids: dict[str, int] = {}
    inv_summary: dict = {}
    pipeline: dict = {}

    print("3/5 Importing Atlas (skip if already completed)...")
    async with async_session_factory() as session:
        import_ids = await _import_atlas(session, fresh=True)
        await ActiveDatasetService(session).set_active(
            products_import_id=import_ids["products"],
            sales_import_id=import_ids["sales"],
            inventory_import_id=import_ids["inventory"],
        )
        await session.commit()

        print("4/5 Running full analysis pipeline...")
        orchestrator = AnalyticsOrchestrator(session)
        selection = {
            "products_import_id": import_ids["products"],
            "sales_import_id": import_ids["sales"],
            "inventory_import_id": import_ids["inventory"],
        }
        pipeline = await orchestrator.run_analysis_pipeline(
            use_cache=False,
            selection=selection,
        )
        if not pipeline.get("success"):
            raise RuntimeError(pipeline.get("message") or "Analysis failed")
        result = pipeline.get("result") or {}
        inv_summary = (result.get("inventory_risk") or {}).get("summary") or {}
        profit = result.get("profit_leakage") or {}
        print(
            f"     dead inventory: ${inv_summary.get('dead_inventory_value', 0):,.0f} "
            f"({inv_summary.get('dead_inventory_count', 0)} SKUs)"
        )
        print(f"     profit leakage: ${profit.get('total_estimated_leakage', 0):,.0f}")

    print("5/5 Syncing landing preview from Atlas engines...")
    import pandas as pd
    from scripts.generate_atlas_demo import (
        SNAPSHOT_PATH,
        compute_analytics_snapshot,
        sync_landing_config,
        update_chart_fallbacks,
    )

    products = pd.read_excel(DEMO_DIR / "atlas_products.xlsx")
    inventory = pd.read_excel(DEMO_DIR / "atlas_inventory.xlsx")
    sales = pd.read_excel(DEMO_DIR / "atlas_sales_q1_2026.xlsx")
    snapshot = compute_analytics_snapshot(products, inventory, sales)
    snapshot["dashboard_pipeline"] = {
        "import_ids": import_ids,
        "inventory_summary": inv_summary,
        "analysis_success": pipeline.get("success"),
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    sync_landing_config(snapshot)
    update_chart_fallbacks(snapshot)
    print(f"     preview revenue: {snapshot['preview']['revenue']}")
    print(f"     preview dead: {snapshot['preview']['deadInventory']}")

    elapsed = round(time.perf_counter() - t0, 1)
    print(f"\nAtlas demo environment ready in {elapsed}s.")
    print("Next: powershell -ExecutionPolicy Bypass -File scripts/build_landing.ps1")


if __name__ == "__main__":
    asyncio.run(main())
