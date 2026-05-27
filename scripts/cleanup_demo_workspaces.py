"""Normalize demo workspace files and remove duplicate demo import records."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import async_session_factory, init_db  # noqa: E402
from app.models.active_analysis import ActiveAnalysisConfig  # noqa: E402
from app.models.import_record import ImportRecord  # noqa: E402
from app.models.inventory import InventoryRecord  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.sales import SalesRecord  # noqa: E402

DEMO_DIR = ROOT / "data" / "demo_companies"

DATASET_MARKERS = ("_inventory", "_products", "_sales")
LEGACY_PREFIXES = ("inventory_", "products_", "sales_")
LEGACY_BRAND_MARKERS = ("nike", "apple", "zara")
ATLAS_FILES = (
    "atlas_products.xlsx",
    "atlas_inventory.xlsx",
    "atlas_sales_q1_2026.xlsx",
)


def purge_legacy_brand_files() -> list[str]:
    """Remove Nike / Apple / Zara XLSX packs from disk (Atlas-only public demo)."""
    actions: list[str] = []
    if not DEMO_DIR.is_dir():
        return actions
    for path in sorted(DEMO_DIR.glob("*.xlsx")):
        lower = path.name.lower()
        if "atlas" in lower:
            continue
        if any(marker in lower for marker in LEGACY_BRAND_MARKERS):
            path.unlink()
            actions.append(f"deleted legacy file {path.name}")
    return actions


def normalize_files() -> list[str]:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    actions.extend(purge_legacy_brand_files())

    for doubled in sorted(DEMO_DIR.glob("*.xlsx.xlsx")):
        target = doubled.with_suffix("")
        if doubled.exists():
            if target.exists():
                doubled.unlink()
                actions.append(f"deleted duplicate {doubled.name}")
            else:
                doubled.replace(target)
                actions.append(f"renamed {doubled.name} -> {target.name}")

    for legacy_path in sorted(DEMO_DIR.glob("*.xlsx")):
        if legacy_path.name.lower().startswith(LEGACY_PREFIXES):
            legacy_path.unlink()
            actions.append(f"deleted legacy {legacy_path.name}")

    return actions


def _is_legacy_brand_import(filename: str) -> bool:
    lower = filename.lower()
    if "atlas" in lower:
        return False
    return any(marker in lower for marker in LEGACY_BRAND_MARKERS)


async def purge_legacy_brand_imports() -> list[str]:
    """Remove Nike / Apple / Zara demo imports; keep Atlas only."""
    actions: list[str] = []
    async with async_session_factory() as session:
        result = await session.execute(select(ImportRecord))
        records = list(result.scalars().all())
        remove = [r for r in records if _is_legacy_brand_import(r.filename)]
        remove_ids = [r.id for r in remove]
        if remove_ids:
            await session.execute(delete(SalesRecord).where(SalesRecord.import_id.in_(remove_ids)))
            await session.execute(delete(InventoryRecord).where(InventoryRecord.import_id.in_(remove_ids)))
            await session.execute(delete(Product).where(Product.import_id.in_(remove_ids)))
            await session.execute(delete(ImportRecord).where(ImportRecord.id.in_(remove_ids)))
            actions.append(
                f"removed {len(remove_ids)} legacy brand import(s): "
                + ", ".join(sorted({r.filename for r in remove})[:6])
                + ("..." if len(remove) > 6 else "")
            )
        await session.commit()
    return actions


async def activate_atlas_workspace() -> list[str]:
    """Point active analysis selection at latest completed Atlas imports."""
    actions: list[str] = []
    async with async_session_factory() as session:
        ids: dict[str, int] = {}
        for filename in ATLAS_FILES:
            dtype = "products" if "products" in filename else "inventory" if "inventory" in filename else "sales"
            result = await session.execute(
                select(ImportRecord)
                .where(ImportRecord.filename == filename, ImportRecord.status == "completed")
                .order_by(ImportRecord.started_at.desc(), ImportRecord.id.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
            if record:
                ids[dtype] = record.id
        if len(ids) == 3:
            from app.services.active_dataset_service import ActiveDatasetService

            await ActiveDatasetService(session).set_active(
                products_import_id=ids["products"],
                sales_import_id=ids["sales"],
                inventory_import_id=ids["inventory"],
            )
            await session.commit()
            actions.append(
                f"active workspace set to Atlas (products={ids['products']}, "
                f"sales={ids['sales']}, inventory={ids['inventory']})"
            )
        else:
            actions.append(f"Atlas imports incomplete — missing: {[t for t in ('products', 'sales', 'inventory') if t not in ids]}")
    return actions


async def cleanup_import_records() -> list[str]:
    actions: list[str] = []

    async with async_session_factory() as session:
        all_result = await session.execute(select(ImportRecord))
        all_records = list(all_result.scalars().all())
        duplicates = [
            record
            for record in all_records
            if record.filename.lower().endswith(".xlsx.xlsx")
            or record.filename.lower().startswith(LEGACY_PREFIXES)
        ]
        duplicate_ids = [record.id for record in duplicates]

        if duplicate_ids:
            await session.execute(delete(SalesRecord).where(SalesRecord.import_id.in_(duplicate_ids)))
            await session.execute(delete(InventoryRecord).where(InventoryRecord.import_id.in_(duplicate_ids)))
            await session.execute(delete(Product).where(Product.import_id.in_(duplicate_ids)))
            await session.execute(delete(ImportRecord).where(ImportRecord.id.in_(duplicate_ids)))
            actions.append(f"removed {len(duplicate_ids)} legacy import record(s)")

        standard_filenames = sorted({
            record.filename
            for record in all_records
            if record.filename.lower().endswith(".xlsx")
            and any(marker in record.filename.lower() for marker in DATASET_MARKERS)
            and not record.filename.lower().startswith(LEGACY_PREFIXES)
        })
        for filename in standard_filenames:
            result = await session.execute(
                select(ImportRecord)
                .where(ImportRecord.filename == filename)
                .order_by(ImportRecord.started_at.desc(), ImportRecord.id.desc())
            )
            records = list(result.scalars().all())
            if len(records) <= 1:
                continue

            keep = records[0]
            remove_ids = [record.id for record in records[1:]]
            await session.execute(delete(SalesRecord).where(SalesRecord.import_id.in_(remove_ids)))
            await session.execute(delete(InventoryRecord).where(InventoryRecord.import_id.in_(remove_ids)))
            await session.execute(delete(Product).where(Product.import_id.in_(remove_ids)))
            await session.execute(delete(ImportRecord).where(ImportRecord.id.in_(remove_ids)))
            await _repair_active_refs(session, remove_ids, keep.id)
            actions.append(f"deduped {filename}, kept import {keep.id}")

        await session.commit()
    return actions


async def _repair_active_refs(session, removed_ids: list[int], keep_id: int) -> None:
    result = await session.execute(select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        return
    removed = set(removed_ids)
    if config.products_import_id in removed:
        config.products_import_id = keep_id
    if config.sales_import_id in removed:
        config.sales_import_id = keep_id
    if config.inventory_import_id in removed:
        config.inventory_import_id = keep_id


async def main() -> None:
    await init_db()
    actions = normalize_files()
    actions.extend(await purge_legacy_brand_imports())
    actions.extend(await cleanup_import_records())
    actions.extend(await activate_atlas_workspace())
    if actions:
        print("\n".join(actions))
    else:
        print("Demo workspaces already clean.")


if __name__ == "__main__":
    asyncio.run(main())
