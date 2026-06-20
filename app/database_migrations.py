"""Lightweight schema migrations for SQLite upgrades and fresh PostgreSQL installs."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.utils.app_timezone import naive_local_now


async def migrate_schema(conn: AsyncConnection, database_url: str) -> None:
    dialect = conn.dialect.name
    await _migrate_import_records(conn, dialect)
    await _migrate_org_columns(conn, dialect)
    await _migrate_billing_columns(conn, dialect)
    await _migrate_user_roles(conn, dialect)
    await _migrate_active_analysis_config(conn, dialect)
    await _ensure_active_analysis_singleton(conn, dialect)
    if await _needs_backfill(conn):
        await _backfill_import_dataset_types(conn)


async def _table_columns(conn: AsyncConnection, table: str, dialect: str) -> set[str]:
    if dialect == "sqlite":
        def column_names(sync_conn):
            rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return {row[1] for row in rows}

        return await conn.run_sync(column_names)

    result = await conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table
            """
        ),
        {"table": table},
    )
    return {row[0] for row in result.all()}


async def _add_column_if_missing(
    conn: AsyncConnection,
    *,
    table: str,
    dialect: str,
    name: str,
    sqlite_type: str,
    postgres_type: str,
) -> None:
    cols = await _table_columns(conn, table, dialect)
    if name in cols:
        return
    col_type = sqlite_type if dialect == "sqlite" else postgres_type
    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"))


async def _ensure_active_analysis_singleton(conn: AsyncConnection, dialect: str) -> None:
    """Guarantee row id=1 exists (fixes UNIQUE errors on concurrent first requests)."""
    updated_at = naive_local_now()
    if dialect == "sqlite":
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO active_analysis_config (id, updated_at) "
                "VALUES (1, :updated_at)"
            ),
            {"updated_at": updated_at},
        )
        return
    await conn.execute(
        text(
            """
            INSERT INTO active_analysis_config (id, updated_at)
            VALUES (1, :updated_at)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"updated_at": updated_at},
    )


async def _migrate_user_roles(conn: AsyncConnection, dialect: str) -> None:
    await _add_column_if_missing(
        conn,
        table="users",
        dialect=dialect,
        name="role",
        sqlite_type="VARCHAR(32) DEFAULT 'owner'",
        postgres_type="VARCHAR(32) DEFAULT 'owner'",
    )
    await conn.execute(
        text("UPDATE users SET role = 'owner' WHERE role IS NULL OR role = ''")
    )


async def _migrate_active_analysis_config(conn: AsyncConnection, dialect: str) -> None:
    await _add_column_if_missing(
        conn,
        table="active_analysis_config",
        dialect=dialect,
        name="analysis_generated_at",
        sqlite_type="DATETIME",
        postgres_type="TIMESTAMP",
    )
    await _add_column_if_missing(
        conn,
        table="active_analysis_config",
        dialect=dialect,
        name="analysis_selection_key",
        sqlite_type="VARCHAR(64)",
        postgres_type="VARCHAR(64)",
    )
    await conn.execute(
        text(
            """
            UPDATE active_analysis_config
            SET analysis_generated_at = NULL
            WHERE analysis_generated_at IS NOT NULL AND analysis_selection_key IS NULL
            """
        )
    )


async def _migrate_import_records(conn: AsyncConnection, dialect: str) -> None:
    alters = [
        ("dataset_type", "VARCHAR(32) DEFAULT 'unknown'", "VARCHAR(32) DEFAULT 'unknown'"),
        ("detection_confidence", "REAL", "DOUBLE PRECISION"),
        ("detection_scores_json", "TEXT", "TEXT"),
        ("needs_type_confirmation", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        ("products_imported", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        ("sales_imported", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        ("inventory_imported", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    ]
    for name, sqlite_type, postgres_type in alters:
        await _add_column_if_missing(
            conn,
            table="import_records",
            dialect=dialect,
            name=name,
            sqlite_type=sqlite_type,
            postgres_type=postgres_type,
        )


async def _migrate_org_columns(conn: AsyncConnection, dialect: str) -> None:
    org_tables = [
        "import_records",
        "products",
        "alerts",
        "analytics_snapshots",
        "users",
    ]
    for table in org_tables:
        cols = await _table_columns(conn, table, dialect)
        if not cols:
            continue
        await _add_column_if_missing(
            conn,
            table=table,
            dialect=dialect,
            name="organization_id",
            sqlite_type="INTEGER",
            postgres_type="INTEGER",
        )


async def _migrate_billing_columns(conn: AsyncConnection, dialect: str) -> None:
    await _add_column_if_missing(
        conn,
        table="organizations",
        dialect=dialect,
        name="stripe_customer_id",
        sqlite_type="VARCHAR(128)",
        postgres_type="VARCHAR(128)",
    )
    await _add_column_if_missing(
        conn,
        table="organizations",
        dialect=dialect,
        name="stripe_subscription_id",
        sqlite_type="VARCHAR(128)",
        postgres_type="VARCHAR(128)",
    )
    await _add_column_if_missing(
        conn,
        table="organizations",
        dialect=dialect,
        name="stripe_price_id",
        sqlite_type="VARCHAR(128)",
        postgres_type="VARCHAR(128)",
    )
    await _add_column_if_missing(
        conn,
        table="organizations",
        dialect=dialect,
        name="stripe_subscription_status",
        sqlite_type="VARCHAR(64)",
        postgres_type="VARCHAR(64)",
    )


async def _needs_backfill(conn: AsyncConnection) -> bool:
    """Run heavy backfill only when imports exist without typed metadata."""
    result = await conn.execute(
        text(
            """
            SELECT 1 FROM import_records
            WHERE dataset_type = 'unknown'
               OR (products_imported = 0 AND sales_imported = 0 AND inventory_imported = 0)
            LIMIT 1
            """
        )
    )
    return result.first() is not None


async def _backfill_import_dataset_types(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
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
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE import_records SET dataset_type = 'products'
            WHERE dataset_type = 'unknown' AND products_imported > 0
              AND sales_imported = 0 AND inventory_imported = 0
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE import_records SET dataset_type = 'sales'
            WHERE dataset_type = 'unknown' AND sales_imported > 0
              AND products_imported = 0 AND inventory_imported = 0
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE import_records SET dataset_type = 'inventory'
            WHERE dataset_type = 'unknown' AND inventory_imported > 0
              AND products_imported = 0 AND sales_imported = 0
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE import_records SET dataset_type = 'mixed'
            WHERE dataset_type = 'unknown'
              AND (products_imported + sales_imported + inventory_imported) > 0
            """
        )
    )
