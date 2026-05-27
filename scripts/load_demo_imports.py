"""Load the public demo Excel library into CommerceFlow import history once.

This is intentionally a one-time utility, not a startup hook. If a user deletes
one of these demo imports from the app, it stays deleted until this script is run
again.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import async_session_factory, init_db  # noqa: E402
from app.models.import_record import ImportRecord  # noqa: E402
from app.services.import_service import ImportService  # noqa: E402

DEMO_DIR = ROOT / "data" / "demo_companies"

# Public demo ships Atlas Retail Group only (enterprise stress-test workspace).
ATLAS_DEMO_FILES = (
    "atlas_products.xlsx",
    "atlas_inventory.xlsx",
    "atlas_sales_q1_2026.xlsx",
)

async def _already_imported(filename: str) -> bool:
    async with async_session_factory() as session:
        result = await session.execute(
            select(ImportRecord.id)
            .where(
                ImportRecord.filename == filename,
                ImportRecord.status == "completed",
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


async def _load_one(filename: str) -> str:
    target = DEMO_DIR / filename
    if not target.is_file():
        raise FileNotFoundError(f"Missing demo file: {target}")

    if await _already_imported(filename):
        return f"SKIP {filename} already imported"

    async with async_session_factory() as session:
        service = ImportService(session)
        record = await service.create_import(filename, "generic", dataset_type="auto")
        record = await service.process_file(record.id, target, "generic")
        if record.status != "completed":
            await session.rollback()
            raise RuntimeError(f"Import failed for {filename}: {record.errors_json}")
        await session.commit()
        return f"OK   {filename} ({record.success_count} rows)"


async def main() -> None:
    await init_db()
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ATLAS_DEMO_FILES:
        print(await _load_one(filename))


if __name__ == "__main__":
    asyncio.run(main())
