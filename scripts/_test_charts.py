import asyncio
import re
import zipfile
from pathlib import Path

from app.database import async_session_factory, init_db
from app.services.export_service import ExportService


async def main():
    await init_db()
    async with async_session_factory() as s:
        b = await ExportService(s).export_enterprise_workbook()
    p = Path("data/exports/_chart_v2.xlsx")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b[0])
    z = zipfile.ZipFile(p)
    for i in (1, 2, 3):
        name = f"xl/charts/chart{i}.xml"
        if name not in z.namelist():
            print(name, "MISSING")
            continue
        xml = z.read(name).decode()
        has_cache = "numCache" in xml or "strCache" in xml
        has_ref = "numRef" in xml or "strRef" in xml
        pts = re.findall(r"ptCount val=", xml)
        vals = re.findall(r"<c:v>([^<]+)</c:v>", xml)[:3]
        print(f"{name}: ref={has_ref} cache={has_cache} ptCount_tags={len(pts)} sample_vals={vals}")
    print("written", p.resolve())


if __name__ == "__main__":
    asyncio.run(main())
