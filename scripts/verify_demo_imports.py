#!/usr/bin/env python3
"""Verify demo datasets import cleanly via ImportService."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_directories
from app.database import async_session_factory, init_db
from app.services.import_service import ImportService

DEMO = ROOT / "data" / "demo_companies"

SETS = [
    ("atlas", "atlas_products.xlsx", "atlas_inventory.xlsx", "atlas_sales_q1_2026.xlsx"),
]


async def import_one(service: ImportService, path: Path, expected: str) -> None:
    record = await service.create_import(path.name, "generic", dataset_type="auto")
    record = await service.process_file(record.id, path, "generic")
    assert record.status == "completed", f"{path.name} failed: {record.errors_json}"
    assert not record.needs_type_confirmation, f"{path.name} needs confirmation"
    assert record.dataset_type == expected, f"{path.name}: expected {expected}, got {record.dataset_type}"
    print(
        f"  OK {path.name}: type={record.dataset_type} "
        f"rows={record.success_count} (p={record.products_imported} s={record.sales_imported} i={record.inventory_imported})"
    )


async def main() -> None:
    ensure_directories()
    await init_db()
    async with async_session_factory() as session:
        service = ImportService(session)
        for label, prod, inv, sales in SETS:
            print(f"\n{label.upper()}")
            await import_one(service, DEMO / prod, "products")
            await import_one(service, DEMO / inv, "inventory")
            await import_one(service, DEMO / sales, "sales")
        await session.commit()
    print("\nAll demo imports passed.")


if __name__ == "__main__":
    asyncio.run(main())
