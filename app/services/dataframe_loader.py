"""Chunked, memory-aware loading of analytics datasets from the database."""

from __future__ import annotations

import time
from typing import Any, TypeVar

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.import_record import ImportRecord
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sales import SalesRecord
from app.services.dataset_bundle import DatasetBundle
from app.utils.analysis_logger import log_performance, log_stage
from app.utils.dataframe_ops import concat_chunks, memory_mb

ModelT = TypeVar("ModelT")


class DataframeLoader:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def load(self, selection: dict[str, int | None]) -> DatasetBundle:
        t0 = time.perf_counter()
        pid = selection.get("products_import_id")
        sid = selection.get("sales_import_id")
        iid = selection.get("inventory_import_id")

        products_df = await self._load_products(pid) if pid else pd.DataFrame()
        sales_df, sales_meta = await self._load_sales(sid) if sid else (pd.DataFrame(), {})
        inventory_df = await self._load_inventory(iid) if iid else pd.DataFrame()

        selected_ids = [x for x in (pid, sid, iid) if x]
        import_rows: list[ImportRecord] = []
        if selected_ids:
            imports_result = await self.session.execute(
                select(ImportRecord).where(ImportRecord.id.in_(selected_ids))
            )
            import_rows = list(imports_result.scalars().all())

        info: dict[str, Any] = {
            "database_path": str(self.settings.database_url),
            "selection": selection,
            "row_counts": {
                "products": len(products_df),
                "sales": int(sales_meta.get("source_row_count", len(sales_df))),
                "inventory": len(inventory_df),
            },
            "load_modes": {
                "products": "full",
                "sales": sales_meta.get("mode", "none"),
                "inventory": "full",
            },
            "sales_meta": sales_meta,
            "selected_imports": [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "dataset_type": r.dataset_type,
                    "source_type": r.source_type,
                    "status": r.status,
                    "row_count": r.row_count,
                    "success_count": r.success_count,
                    "error_count": r.error_count,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                }
                for r in import_rows
            ],
            "active_datasets": {
                "products": pid is not None and len(products_df) > 0,
                "sales": sid is not None and (len(sales_df) > 0 or sales_meta.get("source_row_count", 0) > 0),
                "inventory": iid is not None and len(inventory_df) > 0,
            },
            "memory_mb_after_load": round(memory_mb(), 1),
            "load_duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

        log_performance(
            "load_datasets",
            duration_ms=info["load_duration_ms"],
            memory_mb=info["memory_mb_after_load"],
            products=info["row_counts"]["products"],
            sales=info["row_counts"]["sales"],
            inventory=info["row_counts"]["inventory"],
            sales_mode=sales_meta.get("mode"),
        )
        return DatasetBundle(products=products_df, sales=sales_df, inventory=inventory_df, info=info)

    async def _count(self, model, import_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(model).where(model.import_id == import_id)
        )
        return int(result.scalar() or 0)

    async def _load_products(self, import_id: int) -> pd.DataFrame:
        total = await self._count(Product, import_id)
        if total == 0:
            return pd.DataFrame()
        chunk_size = self.settings.db_fetch_chunk_size
        chunks: list[pd.DataFrame] = []
        offset = 0
        while offset < total:
            result = await self.session.execute(
                select(Product)
                .where(Product.import_id == import_id)
                .order_by(Product.id)
                .offset(offset)
                .limit(chunk_size)
            )
            rows = result.scalars().all()
            if not rows:
                break
            chunks.append(
                pd.DataFrame(
                    [
                        {
                            "sku": p.sku,
                            "title": p.title,
                            "category": p.category,
                            "price": p.price,
                            "cost": p.cost,
                            "margin_pct": p.margin_pct,
                            "compare_at_price": p.compare_at_price,
                        }
                        for p in rows
                    ]
                )
            )
            offset += chunk_size
        return concat_chunks(chunks)

    async def _load_inventory(self, import_id: int) -> pd.DataFrame:
        total = await self._count(InventoryRecord, import_id)
        if total == 0:
            return pd.DataFrame()
        chunk_size = self.settings.db_fetch_chunk_size
        chunks: list[pd.DataFrame] = []
        offset = 0
        while offset < total:
            result = await self.session.execute(
                select(InventoryRecord)
                .where(InventoryRecord.import_id == import_id)
                .order_by(InventoryRecord.id)
                .offset(offset)
                .limit(chunk_size)
            )
            rows = result.scalars().all()
            if not rows:
                break
            chunks.append(
                pd.DataFrame(
                    [
                        {
                            "sku": i.sku,
                            "quantity_on_hand": i.quantity_on_hand,
                            "days_in_stock": i.days_in_stock,
                        }
                        for i in rows
                    ]
                )
            )
            offset += chunk_size
        return concat_chunks(chunks)

    async def _load_sales(self, import_id: int) -> tuple[pd.DataFrame, dict[str, Any]]:
        total = await self._count(SalesRecord, import_id)
        meta: dict[str, Any] = {"source_row_count": total}
        if total == 0:
            meta["mode"] = "empty"
            return pd.DataFrame(), meta

        if total > self.settings.sales_aggregate_above_rows:
            meta["mode"] = "aggregated"
            df = await self._load_sales_aggregated(import_id)
            meta["aggregated_sku_count"] = len(df)
            return df, meta

        meta["mode"] = "detail"
        chunk_size = self.settings.db_fetch_chunk_size
        chunks: list[pd.DataFrame] = []
        offset = 0
        while offset < total:
            result = await self.session.execute(
                select(SalesRecord)
                .where(SalesRecord.import_id == import_id)
                .order_by(SalesRecord.id)
                .offset(offset)
                .limit(chunk_size)
            )
            rows = result.scalars().all()
            if not rows:
                break
            chunks.append(
                pd.DataFrame(
                    [
                        {
                            "sku": s.sku,
                            "quantity": s.quantity,
                            "revenue": s.revenue,
                            "discount_amount": s.discount_amount,
                            "sold_at": s.sold_at,
                            "order_id": s.order_id,
                        }
                        for s in rows
                    ]
                )
            )
            offset += chunk_size
        return concat_chunks(chunks), meta

    async def _load_sales_aggregated(self, import_id: int) -> pd.DataFrame:
        """SKU-level aggregates for million-row sales — vectorized engine input."""
        result = await self.session.execute(
            select(
                SalesRecord.sku.label("sku"),
                func.sum(SalesRecord.quantity).label("quantity"),
                func.sum(SalesRecord.revenue).label("revenue"),
                func.sum(SalesRecord.discount_amount).label("discount_amount"),
                func.count(func.distinct(SalesRecord.order_id)).label("order_count"),
                func.min(SalesRecord.sold_at).label("sold_at_min"),
                func.max(SalesRecord.sold_at).label("sold_at_max"),
            )
            .where(SalesRecord.import_id == import_id)
            .group_by(SalesRecord.sku)
        )
        rows = result.all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "sku": r.sku,
                    "quantity": int(r.quantity or 0),
                    "revenue": float(r.revenue or 0),
                    "discount_amount": float(r.discount_amount or 0),
                    "order_count": int(r.order_count or 0),
                    "sold_at": r.sold_at_max,
                    "aggregated": True,
                }
                for r in rows
            ]
        )

    async def load_sales_daily_revenue(self, import_id: int, limit_days: int = 366) -> pd.DataFrame:
        """SQL aggregation for charts — never loads full transaction table."""
        result = await self.session.execute(
            select(
                func.date(SalesRecord.sold_at).label("date"),
                func.sum(SalesRecord.revenue).label("revenue"),
            )
            .where(SalesRecord.import_id == import_id)
            .group_by(func.date(SalesRecord.sold_at))
            .order_by(func.date(SalesRecord.sold_at).desc())
            .limit(limit_days)
        )
        rows = result.all()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([{"date": str(r.date), "revenue": float(r.revenue or 0)} for r in rows])
        return df.sort_values("date")
