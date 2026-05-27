#!/usr/bin/env python3
"""Generate, import, analyze, and benchmark Atlas Retail Group stress-test datasets."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_directories  # noqa: E402
from app.database import async_session_factory, init_db  # noqa: E402
from app.services.active_dataset_service import ActiveDatasetService  # noqa: E402
from app.services.alert_service import AlertService  # noqa: E402
from app.services.analytics_orchestrator import AnalyticsOrchestrator  # noqa: E402
from app.services.export_service import ExportService  # noqa: E402
from app.services.import_service import ImportService  # noqa: E402
from app.utils.cache import analytics_cache  # noqa: E402
from app.utils.dataframe_ops import memory_mb  # noqa: E402

DEMO_DIR = ROOT / "data" / "demo_companies"
LOG_DIR = ROOT / "logs"
ATLAS_FILES = (
    "atlas_products.xlsx",
    "atlas_inventory.xlsx",
    "atlas_sales_q1_2026.xlsx",
)


def _ensure_generated() -> float:
    missing = [name for name in ATLAS_FILES if not (DEMO_DIR / name).is_file()]
    if not missing:
        return 0.0
    print(f"Missing Atlas files ({', '.join(missing)}). Running generator...")
    t0 = time.perf_counter()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_atlas_demo.py")],
        check=True,
        cwd=str(ROOT),
    )
    return round(time.perf_counter() - t0, 2)


async def _import_atlas(session) -> tuple[dict[str, int], dict[str, float]]:
    service = ImportService(session)
    ids: dict[str, int] = {}
    timings: dict[str, float] = {}
    type_map = {
        "atlas_products.xlsx": "products",
        "atlas_inventory.xlsx": "inventory",
        "atlas_sales_q1_2026.xlsx": "sales",
    }
    for filename, dtype in type_map.items():
        path = DEMO_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        t0 = time.perf_counter()
        record = await service.create_import(filename, "generic", dataset_type="auto")
        record = await service.process_file(record.id, path, "generic")
        elapsed = round(time.perf_counter() - t0, 2)
        timings[filename] = elapsed
        if record.status != "completed":
            raise RuntimeError(f"Import failed for {filename}: {record.errors_json}")
        ids[dtype] = record.id
        print(
            f"  OK {filename}: {record.success_count:,} rows in {elapsed}s "
            f"(p={record.products_imported} s={record.sales_imported} i={record.inventory_imported})"
        )
    return ids, timings


async def _maybe_http_checks() -> dict:
    """Optional live-server checks when uvicorn is already running."""
    import urllib.error
    import urllib.request

    base = "http://127.0.0.1:8000"
    paths = [
        "/dashboard",
        "/api/analytics/dashboard",
        "/api/analytics/full",
        "/api/alerts",
        "/api/exports/meta",
    ]
    results: dict[str, object] = {}
    for path in paths:
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=30) as response:
                results[path] = response.status
        except urllib.error.HTTPError as exc:
            results[path] = exc.code
        except Exception as exc:  # noqa: BLE001
            results["skipped"] = str(exc)
            break
    return results


async def main() -> None:
    ensure_directories()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    total_t0 = time.perf_counter()
    tracemalloc.start()

    gen_s = _ensure_generated()
    await init_db()

    metrics: dict[str, object] = {
        "company": "Atlas Retail Group",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "generation_seconds": gen_s,
    }

    async with async_session_factory() as session:
        print("\nImporting Atlas datasets...")
        import_t0 = time.perf_counter()
        import_ids, import_timings = await _import_atlas(session)
        await session.commit()
        import_total = round(time.perf_counter() - import_t0, 2)
        metrics["import"] = {
            "per_file_seconds": import_timings,
            "total_seconds": import_total,
            "import_ids": import_ids,
        }

        active_svc = ActiveDatasetService(session)
        await active_svc.set_active(
            products_import_id=import_ids["products"],
            sales_import_id=import_ids["sales"],
            inventory_import_id=import_ids["inventory"],
        )
        analytics_cache.invalidate()

        print("\nRunning full analysis pipeline...")
        analysis_t0 = time.perf_counter()
        orchestrator = AnalyticsOrchestrator(session)
        pipeline = await orchestrator.run_analysis_pipeline(
            use_cache=False,
            selection={
                "products_import_id": import_ids["products"],
                "sales_import_id": import_ids["sales"],
                "inventory_import_id": import_ids["inventory"],
            },
        )
        analysis_s = round(time.perf_counter() - analysis_t0, 2)
        result = pipeline.get("result") or {}
        metrics["analysis"] = {
            "seconds": analysis_s,
            "stages": pipeline.get("stages", []),
            "profit_issues": len((result.get("profit_leakage") or {}).get("issues", [])),
            "inventory_alerts": len((result.get("inventory_risk") or {}).get("alerts", [])),
            "data_quality_issues": len((result.get("data_cleaning") or {}).get("issues", [])),
        }

        print("\nGenerating operational alerts...")
        alert_svc = AlertService(session)
        alerts = await alert_svc.generate_from_analysis()
        await session.commit()
        metrics["alerts_generated"] = len(alerts)

        print("\nGenerating enterprise export workbook...")
        export_t0 = time.perf_counter()
        export_svc = ExportService(session)
        workbook_bytes, workbook_name, _mime = await export_svc.export_enterprise_workbook()
        export_s = round(time.perf_counter() - export_t0, 2)
        metrics["export"] = {
            "seconds": export_s,
            "filename": workbook_name,
            "bytes": len(workbook_bytes),
        }

        info = await orchestrator.get_dataset_info()
        metrics["dataset_info"] = info

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_s = round(time.perf_counter() - total_t0, 2)
    metrics["memory"] = {
        "tracemalloc_current_mb": round(current / (1024 * 1024), 2),
        "tracemalloc_peak_mb": round(peak / (1024 * 1024), 2),
        "dataframe_loader_mb": memory_mb(),
    }
    metrics["total_seconds"] = total_s
    metrics["success"] = True
    metrics["sales_rows_target"] = 100_000

    print("\nOptional HTTP checks (dashboard / charts / alerts / export meta)...")
    metrics["http_checks"] = await _maybe_http_checks()

    log_path = LOG_DIR / "atlas_stress_test.json"
    log_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\n=== Atlas Stress Test Summary ===")
    print(f"  Generation:  {gen_s}s")
    print(f"  Import:      {import_total}s")
    for fname, sec in import_timings.items():
        print(f"    - {fname}: {sec}s")
    print(f"  Analysis:    {analysis_s}s")
    print(f"  Export:      {export_s}s")
    print(f"  Total:       {total_s}s")
    print(f"  Peak memory: {metrics['memory']['tracemalloc_peak_mb']} MB")
    print(f"  Alerts:      {metrics['alerts_generated']}")
    print(f"  Log:         {log_path}")
    print("\nAtlas 100k stress test PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
