"""Load sample CSV data into CommerceFlow for demo purposes."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import ensure_directories, get_settings
from app.database import async_session_factory, init_db
from app.services.import_service import ImportService


async def seed():
    ensure_directories()
    await init_db()
    data_dir = Path("data/sample")
    files = [
        ("products_sample.csv", "generic"),
        ("sales_sample.csv", "generic"),
        ("inventory_sample.csv", "generic"),
    ]
    async with async_session_factory() as session:
        service = ImportService(session)
        for filename, source in files:
            path = data_dir / filename
            if not path.exists():
                print(f"Skip missing: {path}")
                continue
            record = await service.create_import(filename, source)
            await service.process_file(record.id, path, source)
            print(f"Imported {filename}: {record.status}")
        await session.commit()
    print("Sample data loaded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
