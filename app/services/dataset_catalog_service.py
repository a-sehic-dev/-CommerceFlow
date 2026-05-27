from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_record import ImportRecord
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sales import SalesRecord
from app.schemas.datasets import ImportCatalogItem, ImportCatalogResponse
from app.utils.dataset_display import (
    dataset_source_label,
    detect_company_name,
    format_dataset_metadata,
    is_internal_dataset,
    module_engine_title,
    module_status_label,
    resolve_display_name,
)


def _format_label(filename: str, rows: int, started_at) -> str:
    ts = started_at.strftime("%I:%M %p") if started_at else ""
    return f"{filename} (operational dataset • {ts})"


def _format_subtitle(rows: int, started_at, dtype: str, filename: str) -> str:
    return format_dataset_metadata(
        rows=rows,
        started_at=started_at,
        filename=filename,
        dataset_type=dtype,
    )


def _eligible_types(counts: dict[str, int]) -> list[str]:
    types = []
    if counts.get("sales", 0) > 0:
        types.append("sales")
    if counts.get("products", 0) > 0:
        types.append("products")
    if counts.get("inventory", 0) > 0:
        types.append("inventory")
    return types


def _primary_type(counts: dict[str, int]) -> str:
    eligible = _eligible_types(counts)
    if len(eligible) == 1:
        return eligible[0]
    if len(eligible) > 1:
        return "mixed"
    return "unknown"


def _catalog_eligible(record: ImportRecord, counts: dict[str, int]) -> list[str]:
    """Bucket imports by detected dataset type (column-based), not filename."""
    if record.needs_type_confirmation:
        return []
    stored = record.dataset_type or "unknown"
    if stored in ("products", "sales", "inventory"):
        if counts.get(stored, 0) > 0 or (record.success_count or 0) > 0:
            return [stored]
        return []
    if stored == "mixed":
        return _eligible_types(counts)
    return _eligible_types(counts)


def build_catalog_item(record: ImportRecord, counts: dict[str, int]) -> ImportCatalogItem:
    total_rows = counts["products"] + counts["sales"] + counts["inventory"]
    stored = record.dataset_type or "unknown"
    dtype = stored if stored in ("products", "sales", "inventory", "mixed") else _primary_type(counts)
    rows = total_rows or record.success_count or record.row_count
    eligible = _catalog_eligible(record, counts)
    display = resolve_display_name(record.filename, dtype)
    company = detect_company_name(record.filename)
    return ImportCatalogItem(
        id=record.id,
        filename=record.filename,
        display_name=display,
        company_name=company,
        source_label=dataset_source_label(record.filename),
        engine_title=module_engine_title(dtype),
        status_label=module_status_label(dtype),
        dataset_type=dtype,
        status=record.status,
        row_count=record.row_count,
        success_count=rows,
        products_imported=counts["products"],
        sales_imported=counts["sales"],
        inventory_imported=counts["inventory"],
        started_at=record.started_at,
        label=_format_label(display, rows, record.started_at),
        eligible_for=eligible,
        subtitle=_format_subtitle(rows, record.started_at, dtype, record.filename),
        detection_confidence=record.detection_confidence,
        needs_type_confirmation=bool(record.needs_type_confirmation),
    )


# Back-compat alias for active_dataset_service
_to_item = build_catalog_item


class DatasetCatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _row_counts_by_import(self) -> dict[int, dict[str, int]]:
        counts: dict[int, dict[str, int]] = {}

        for model, key in [(Product, "products"), (SalesRecord, "sales"), (InventoryRecord, "inventory")]:
            result = await self.session.execute(
                select(model.import_id, func.count())
                .where(model.import_id.isnot(None))
                .group_by(model.import_id)
            )
            for import_id, cnt in result.all():
                if import_id is None:
                    continue
                counts.setdefault(import_id, {"products": 0, "sales": 0, "inventory": 0})
                counts[import_id][key] = int(cnt)
        return counts

    async def item_for_import_id(self, import_id: int) -> ImportCatalogItem | None:
        record = await self.get_import(import_id)
        if not record:
            return None
        db_counts = await self._row_counts_by_import()
        counts = db_counts.get(
            import_id,
            {
                "products": record.products_imported or 0,
                "sales": record.sales_imported or 0,
                "inventory": record.inventory_imported or 0,
            },
        )
        return build_catalog_item(record, counts)

    async def list_catalog(self, completed_only: bool = True) -> ImportCatalogResponse:
        q = select(ImportRecord).order_by(ImportRecord.started_at.desc())
        if completed_only:
            q = q.where(ImportRecord.status.in_(["completed"]))
        result = await self.session.execute(q)
        records = list(result.scalars().all())
        db_counts = await self._row_counts_by_import()

        products: list[ImportCatalogItem] = []
        sales: list[ImportCatalogItem] = []
        inventory: list[ImportCatalogItem] = []
        all_items: list[ImportCatalogItem] = []

        for r in records:
            if is_internal_dataset(r.filename):
                continue
            if r.needs_type_confirmation:
                continue
            counts = db_counts.get(r.id, {"products": 0, "sales": 0, "inventory": 0})
            total_rows = counts["products"] + counts["sales"] + counts["inventory"]
            if total_rows == 0 and (r.success_count or 0) == 0:
                continue

            item = build_catalog_item(r, counts)
            eligible = item.eligible_for
            if not eligible:
                continue
            all_items.append(item)

            if "products" in eligible:
                products.append(item)
            if "sales" in eligible:
                sales.append(item)
            if "inventory" in eligible:
                inventory.append(item)

        return ImportCatalogResponse(
            products=products,
            sales=sales,
            inventory=inventory,
            all=all_items,
        )

    async def get_import(self, import_id: int) -> ImportRecord | None:
        result = await self.session.execute(
            select(ImportRecord).where(ImportRecord.id == import_id)
        )
        return result.scalar_one_or_none()

    async def validate_selection_for_type(self, import_id: int, expected_type: str) -> bool:
        record = await self.get_import(import_id)
        if not record or record.needs_type_confirmation:
            return False
        stored = record.dataset_type
        if stored in ("products", "sales", "inventory"):
            return stored == expected_type
        db_counts = await self._row_counts_by_import()
        counts = db_counts.get(import_id, {})
        return expected_type in _eligible_types(counts)
