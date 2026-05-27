"""Lightweight SQLite schema migrations for existing databases."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def migrate_schema(conn: AsyncConnection) -> None:
    await _migrate_import_records(conn)
    await _migrate_active_analysis_config(conn)
    if await _needs_backfill(conn):
        await _backfill_import_dataset_types(conn)


async def _migrate_active_analysis_config(conn: AsyncConnection) -> None:
    def column_names(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(active_analysis_config)")).fetchall()
        return {row[1] for row in rows}

    cols = await conn.run_sync(column_names)
    if "analysis_generated_at" not in cols:
        await conn.execute(
            text("ALTER TABLE active_analysis_config ADD COLUMN analysis_generated_at DATETIME")
        )
    if "analysis_selection_key" not in cols:
        await conn.execute(
            text("ALTER TABLE active_analysis_config ADD COLUMN analysis_selection_key VARCHAR(64)")
        )
        await conn.execute(
            text("""
            UPDATE active_analysis_config
            SET analysis_generated_at = NULL
            WHERE analysis_generated_at IS NOT NULL AND analysis_selection_key IS NULL
            """)
        )


async def _needs_backfill(conn: AsyncConnection) -> bool:
    """Run heavy backfill only when imports exist without typed metadata."""
    result = await conn.execute(
        text("""
        SELECT 1 FROM import_records
        WHERE dataset_type = 'unknown'
           OR (products_imported = 0 AND sales_imported = 0 AND inventory_imported = 0)
        LIMIT 1
        """)
    )
    return result.first() is not None


async def _migrate_import_records(conn: AsyncConnection) -> None:
    def column_names(sync_conn):
        rows = sync_conn.execute(text("PRAGMA table_info(import_records)")).fetchall()
        return {row[1] for row in rows}

    cols = await conn.run_sync(column_names)
    alters = [
        ("dataset_type", "VARCHAR(32) DEFAULT 'unknown'"),
        ("detection_confidence", "REAL"),
        ("detection_scores_json", "TEXT"),
        ("needs_type_confirmation", "INTEGER DEFAULT 0"),
        ("products_imported", "INTEGER DEFAULT 0"),
        ("sales_imported", "INTEGER DEFAULT 0"),
        ("inventory_imported", "INTEGER DEFAULT 0"),
    ]
    for name, typedef in alters:
        if name not in cols:
            await conn.execute(text(f"ALTER TABLE import_records ADD COLUMN {name} {typedef}"))


async def _backfill_import_dataset_types(conn: AsyncConnection) -> None:
    await conn.execute(
        text("""
        UPDATE import_records SET
            products_imported = (
                SELECT COUNT(*) FROM products WHERE products.import_id = import_records.id
            ),
            sales_imported = (
                SELECT COUNT(*) FROM sales_records WHERE sales_records.import_id = import_records.id
            ),
            inventory_imported = (
                SELECT COUNT(*) FROM inventory_records WHERE inventory_records.import_id = import_records.id
            )
        WHERE products_imported = 0 AND sales_imported = 0 AND inventory_imported = 0
           OR dataset_type = 'unknown'
        """)
    )
    await conn.execute(
        text("""
        UPDATE import_records SET dataset_type = 'products'
        WHERE dataset_type = 'unknown' AND products_imported > 0
          AND sales_imported = 0 AND inventory_imported = 0
        """)
    )
    await conn.execute(
        text("""
        UPDATE import_records SET dataset_type = 'sales'
        WHERE dataset_type = 'unknown' AND sales_imported > 0
          AND products_imported = 0 AND inventory_imported = 0
        """)
    )
    await conn.execute(
        text("""
        UPDATE import_records SET dataset_type = 'inventory'
        WHERE dataset_type = 'unknown' AND inventory_imported > 0
          AND products_imported = 0 AND sales_imported = 0
        """)
    )
    await conn.execute(
        text("""
        UPDATE import_records SET dataset_type = 'mixed'
        WHERE dataset_type = 'unknown'
          AND (products_imported + sales_imported + inventory_imported) > 0
        """)
    )
