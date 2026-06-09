import json

from datetime import datetime

from app.utils.app_timezone import naive_local_now

from pathlib import Path



import pandas as pd

from sqlalchemy import delete, select

from sqlalchemy.ext.asyncio import AsyncSession



from app.config import get_settings
from app.constants import import_status as ST

from app.engines.data_cleaning import DataCleaningEngine

from app.models.import_record import ImportRecord

from app.models.inventory import InventoryRecord

from app.models.product import Product

from app.models.sales import SalesRecord

from app.services.dataset_classifier import (
    CONFIDENCE_MIN,
    ClassificationResult,
    classify_dataset,
    infer_importer_flags,
)

from app.utils.normalization import normalize_sku, normalize_title, safe_float, safe_int
from app.utils.schema_mapper import detect_schema, map_dataframe
from app.utils.analysis_logger import log_performance, log_stage
from app.utils.db_retry import flush_session
from app.utils.file_types import resolve_upload_suffix
from app.utils.import_logger import (
    log_dataset_classification,
    log_import_complete,
    log_import_failed,
    log_import_stage,
    log_import_status,
)



COLUMN_MAPS = {

    "shopify": {

        "sku": ["Variant SKU", "SKU", "sku"],

        "title": ["Title", "title", "Product Title", "product_name"],

        "price": ["Variant Price", "Price", "price", "unit_price"],

        "compare_at_price": ["Variant Compare At Price", "Compare At Price"],

        "cost": ["Cost per item", "cost"],

        "category": ["Product Category", "Type", "category"],

        "vendor": ["Vendor", "vendor"],

        "order_id": ["Name", "Order ID", "order_id", "order_number"],

        "revenue": ["Total", "revenue"],

        "quantity": ["Lineitem quantity", "quantity", "qty"],

        "sold_at": ["Created at", "sold_at", "order_date"],

        "customer": ["Email", "customer", "customer_name"],

        "sales_channel": ["Source", "sales_channel", "channel"],

        "status": ["Status", "status"],

        "margin": ["margin", "profit_margin"],

    },

    "woocommerce": {

        "sku": ["SKU", "sku"],

        "title": ["Name", "title", "Product", "product_name"],

        "price": ["Regular price", "Price", "price", "unit_price"],

        "compare_at_price": ["Sale price"],

        "cost": ["Cost"],

        "category": ["Categories", "category"],

        "order_id": ["Order ID", "order_id", "order_number"],

        "revenue": ["Order total", "revenue", "total"],

        "quantity": ["Quantity", "quantity", "qty"],

        "sold_at": ["Date", "sold_at", "order_date"],

        "customer": ["Billing Email", "customer", "customer_name"],

        "sales_channel": ["Payment method", "channel", "sales_channel"],

        "status": ["Status", "status"],

    },

    "generic": {

        "sku": ["sku", "SKU", "product_sku", "item_sku"],

        "title": ["title", "name", "product_name", "Title", "product"],

        "price": ["price", "unit_price", "Price", "retail_price"],

        "cost": ["cost", "unit_cost", "Cost"],

        "category": ["category", "Category", "product_category"],

        "quantity": ["quantity", "qty", "units_sold", "units"],

        "revenue": ["revenue", "total", "line_total", "sales_amount"],

        "sold_at": ["sold_at", "date", "order_date", "created_at", "sale_date"],

        "order_id": ["order_id", "order_number", "order_no", "order #"],

        "customer": ["customer", "customer_name", "customer_id", "buyer", "email"],

        "sales_channel": ["sales_channel", "channel", "source", "platform", "marketplace"],
        "discount_amount": ["discount_amount", "discount", "discounts", "discount_total", "line_discount"],

        "margin": ["margin", "margin_pct", "profit_margin", "gross_margin"],

        "status": ["status", "product_status", "active", "published"],

        "warehouse": ["warehouse", "location", "fulfillment_center", "store"],

        "on_hand": ["on_hand", "quantity_on_hand", "qty_on_hand", "stock_on_hand"],

        "available_units": ["available_units", "available", "available_stock", "sellable"],

        "reserved": ["reserved", "quantity_reserved", "reserved_qty", "allocated"],

        "inbound": ["inbound", "incoming", "on_order", "expected"],

        "stock": ["stock", "inventory", "units_on_hand"],

        "days_in_stock": ["days_in_stock", "days_in_inventory", "aging_days"],

    },

}





class ImportService:

    def __init__(self, session: AsyncSession):

        self.session = session

        self.settings = get_settings()

        self.cleaner = DataCleaningEngine()



    async def create_import(
        self,
        filename: str,
        source_type: str,
        dataset_type: str = "auto",
        organization_id: int | None = None,
    ) -> ImportRecord:
        record = ImportRecord(
            filename=filename,
            source_type=source_type,
            dataset_type=dataset_type if dataset_type not in ("auto", "") else "unknown",
            status=ST.IMPORTING,
            organization_id=organization_id,
        )

        self.session.add(record)

        await flush_session(self.session, label="create_import")

        return record

    async def get_import(self, import_id: int) -> ImportRecord | None:
        result = await self.session.execute(
            select(ImportRecord).where(ImportRecord.id == import_id)
        )
        return result.scalar_one_or_none()

    async def mark_failed(self, import_id: int, message: str) -> ImportRecord:
        record = await self.get_import(import_id)
        if not record:
            raise ValueError(f"Import {import_id} not found")
        await self._clear_import_data(import_id)
        record.status = ST.FAILED
        record.error_count = 1
        record.errors_json = json.dumps([message])
        record.completed_at = naive_local_now()
        await flush_session(self.session, label="mark_failed")
        log_import_status(import_id, ST.FAILED, message)
        return record

    async def _flush(self, label: str = "import") -> None:
        await flush_session(self.session, label=label)



    async def process_file(

        self,

        import_id: int,

        file_path: Path,

        source_type: str,

        *,

        forced_type: str | None = None,

    ) -> ImportRecord:

        result = await self.session.execute(select(ImportRecord).where(ImportRecord.id == import_id))

        record = result.scalar_one()

        errors: list[str] = []
        import_id = record.id
        self._import_organization_id = record.organization_id

        try:
            import time

            t0 = time.perf_counter()
            log_import_stage(import_id, "classification_started", path=str(file_path))
            record.status = ST.PROCESSING
            await self._flush("import-processing")
            log_import_status(import_id, ST.PROCESSING)
            log_import_stage(import_id, "workbook_parsing_started")
            self._seen_product_skus: set[str] = set()
            self._seen_inventory_skus: set[str] = set()
            first_chunk = True
            raw_headers: list[str] = []
            mapped_columns: list[str] = []
            total_rows = 0
            products_count = sales_count = inv_count = 0
            import_type = "unknown"
            classification = None
            declared = forced_type or record.dataset_type
            user_declared = declared not in ("auto", "unknown", "mixed", "")

            for chunk in self._iter_file_chunks(file_path):
                total_rows += len(chunk)
                if first_chunk:
                    log_import_stage(import_id, "workbook_parsing_first_chunk", rows=len(chunk))
                    raw_headers = list(chunk.columns)
                    schema = detect_schema(raw_headers)
                    log_stage("import", "Schema detected", columns=len(raw_headers), mapped=schema.get("canonical_present"))
                mapped = self._map_columns(chunk, source_type)
                mapped_columns = list(mapped.columns)
                mapped = self.cleaner.normalize_dataframe(mapped)

                if first_chunk:
                    combined_headers = list(dict.fromkeys(raw_headers + list(mapped.columns)))
                    declared_for_detect = forced_type or (declared if user_declared else None)
                    classification = classify_dataset(
                        combined_headers,
                        schema=schema,
                        declared_type=declared_for_detect,
                    )
                    log_dataset_classification(
                        import_id,
                        primary_type=classification.primary_type,
                        confidence=classification.confidence,
                        reason=classification.reason,
                        method=classification.method,
                        scores=classification.scores,
                        needs_confirmation=classification.needs_confirmation,
                    )
                    import_type = self._resolve_import_type(declared, classification, forced_type)
                    record.dataset_type = import_type if import_type != "pending" else "unknown"
                    record.detection_confidence = classification.confidence
                    record.detection_scores_json = json.dumps(classification.to_storage_dict())
                    record.needs_type_confirmation = (
                        classification.needs_confirmation and not user_declared and not forced_type
                    )
                    if record.needs_type_confirmation:
                        record.status = ST.PENDING_CONFIRM
                        record.row_count = total_rows
                        record.success_count = 0
                        record.completed_at = naive_local_now()
                        await self._flush("import-pending-confirm")
                        log_import_status(import_id, ST.PENDING_CONFIRM)
                        return record
                    await self._clear_import_data(import_id)
                    first_chunk = False

                flags = infer_importer_flags(
                    list(mapped.columns), import_type, classification
                )
                if flags.get("products"):
                    products_count += await self._import_products(mapped, import_id)
                if flags.get("sales"):
                    sales_count += await self._import_sales_if_present(mapped, import_id)
                if flags.get("inventory"):
                    inv_count += await self._import_inventory_if_present(mapped, import_id)

            if first_chunk:
                raise ValueError("File is empty or could not be parsed")

            log_import_stage(
                import_id,
                "workbook_parsing_completed",
                total_rows=total_rows,
                products=products_count,
                sales=sales_count,
                inventory=inv_count,
            )

            total_imported = products_count + sales_count + inv_count
            if total_imported == 0 and total_rows > 0:
                if user_declared or forced_type:
                    raise ValueError(
                        f"Could not import any rows as {import_type}. "
                        "Check that column headers match that dataset type, or choose Auto-detect."
                    )
                record.needs_type_confirmation = True
                record.status = ST.PENDING_CONFIRM
                record.row_count = total_rows
                record.success_count = 0
                record.completed_at = naive_local_now()
                await self._flush("import-no-rows-pending")
                log_import_status(
                    import_id,
                    ST.PENDING_CONFIRM,
                    "No rows imported — confirm dataset type to map columns correctly.",
                )
                return record

            record.products_imported = products_count
            record.sales_imported = sales_count
            record.inventory_imported = inv_count
            record.dataset_type = self._finalize_dataset_type(
                import_type, products_count, sales_count, inv_count
            )
            record.needs_type_confirmation = False
            record.status = ST.COMPLETED
            record.row_count = total_rows
            record.success_count = products_count + sales_count + inv_count
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            log_import_complete(
                import_id,
                duration_ms=duration_ms,
                row_count=total_rows,
                products=products_count,
                sales=sales_count,
                inventory=inv_count,
                dataset_type=record.dataset_type,
            )
            log_performance(
                "import_file",
                duration_ms=duration_ms,
                rows=total_rows,
                products=products_count,
                sales=sales_count,
                inventory=inv_count,
            )

            record.error_count = len(errors)

            record.completed_at = naive_local_now()

        except Exception as e:
            log_import_failed(import_id, e)
            await self._clear_import_data(import_id)
            record.status = ST.FAILED
            errors.append(str(e))
            record.error_count = max(1, len(errors))
            record.completed_at = naive_local_now()
            log_import_status(import_id, ST.FAILED, str(e))

        record.errors_json = json.dumps(errors) if errors else None

        await self._flush("import-finalize")

        return record



    async def confirm_dataset_type(

        self, import_id: int, dataset_type: str, file_path: Path, source_type: str

    ) -> ImportRecord:

        if dataset_type not in ("products", "sales", "inventory"):

            raise ValueError("dataset_type must be products, sales, or inventory")

        result = await self.session.execute(select(ImportRecord).where(ImportRecord.id == import_id))

        record = result.scalar_one()

        record.dataset_type = dataset_type

        record.needs_type_confirmation = False

        await self._flush("confirm-type")

        return record



    async def _clear_import_data(self, import_id: int) -> None:

        await self.session.execute(delete(Product).where(Product.import_id == import_id))

        await self.session.execute(delete(SalesRecord).where(SalesRecord.import_id == import_id))

        await self.session.execute(

            delete(InventoryRecord).where(InventoryRecord.import_id == import_id)

        )

        await self._flush("clear-import-data")

    def _resolve_import_type(

        self,

        declared: str,

        classification: ClassificationResult,

        forced_type: str | None,

    ) -> str:

        if forced_type in ("products", "sales", "inventory"):

            return forced_type

        if declared in ("products", "sales", "inventory"):

            return declared

        if classification.is_confident:
            return classification.primary_type

        if classification.primary_type == "mixed":
            return "mixed"

        if classification.primary_type in ("sales", "products", "inventory"):
            if classification.confidence >= CONFIDENCE_MIN:
                return classification.primary_type

        schema_present = set(classification.schema_present or [])
        if schema_present:
            domain_scores = {
                "sales": len(schema_present & {"revenue", "order_id", "sold_at", "quantity"}),
                "products": len(schema_present & {"sku", "title", "price"}),
                "inventory": len(schema_present & {"on_hand", "stock", "warehouse", "sku"}),
            }
            best = max(domain_scores, key=domain_scores.get)
            if domain_scores[best] >= 2:
                return best

        return classification.primary_type if classification.confidence >= 0.34 else "pending"



    def _finalize_dataset_type(

        self, import_type: str, products: int, sales: int, inventory: int

    ) -> str:

        if import_type in ("products", "sales", "inventory"):

            return import_type

        if products and not sales and not inventory:

            return "products"

        if sales and not products and not inventory:

            return "sales"

        if inventory and not products and not sales:

            return "inventory"

        if sum(1 for x in (products, sales, inventory) if x) > 1:

            return "mixed"

        return import_type or "unknown"



    def _iter_file_chunks(self, path: Path):
        suffix = resolve_upload_suffix(path.name)
        chunk_size = self.settings.import_csv_chunk_size
        if suffix == ".csv":
            last_err = None
            for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    reader = pd.read_csv(
                        path,
                        chunksize=chunk_size,
                        encoding=encoding,
                        on_bad_lines="skip",
                        low_memory=False,
                    )
                    for chunk in reader:
                        yield chunk
                    return
                except UnicodeDecodeError as exc:
                    last_err = exc
            if last_err:
                raise last_err
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
            for start in range(0, len(df), chunk_size):
                yield df.iloc[start : start + chunk_size].copy()
            return
        raise ValueError(f"Unsupported file type: {suffix}")

    def _map_columns(self, df: pd.DataFrame, source_type: str) -> pd.DataFrame:
        extra = COLUMN_MAPS.get(source_type, COLUMN_MAPS["generic"])
        return map_dataframe(df, extra_maps=extra)



    async def _import_products(self, df: pd.DataFrame, import_id: int) -> int:

        if "sku" not in df.columns:

            return 0

        work = df.drop_duplicates(subset=["sku"])
        batch: list[Product] = []
        flush_size = self.settings.import_flush_batch_size
        count = 0
        for row in work.to_dict("records"):
            sku = normalize_sku(str(row.get("sku", "")))
            if not sku or sku in self._seen_product_skus:
                continue
            self._seen_product_skus.add(sku)
            price = safe_float(row.get("price") or row.get("unit_price"))
            cost = safe_float(row.get("cost")) if pd.notna(row.get("cost")) else None
            margin = safe_float(row.get("margin")) if pd.notna(row.get("margin")) else None
            if margin is None and cost and price:
                margin = ((price - cost) / price * 100) if price else None
            batch.append(
                Product(
                    sku=sku,
                    title=str(row.get("title", sku)),
                    normalized_title=normalize_title(str(row.get("title", sku))),
                    category=str(row.get("category", "")) if pd.notna(row.get("category")) else None,
                    vendor=str(row.get("vendor", "")) if pd.notna(row.get("vendor")) else None,
                    price=price,
                    compare_at_price=safe_float(row.get("compare_at_price"))
                    if pd.notna(row.get("compare_at_price"))
                    else None,
                    cost=cost,
                    margin_pct=margin,
                    import_id=import_id,
                    organization_id=getattr(self, "_import_organization_id", None),
                )
            )
            count += 1
            if len(batch) >= flush_size:
                self.session.add_all(batch)
                await self._flush("products-batch")
                batch.clear()
        if batch:
            self.session.add_all(batch)
            await self._flush("products-batch")
        return count



    async def _import_sales_if_present(self, df: pd.DataFrame, import_id: int) -> int:

        if "revenue" not in df.columns and "quantity" not in df.columns and "order_id" not in df.columns:

            return 0

        batch: list[SalesRecord] = []
        flush_size = self.settings.import_flush_batch_size
        count = 0
        for row in df.to_dict("records"):
            sku = normalize_sku(str(row.get("sku", ""))) if row.get("sku") is not None else ""
            if not sku and not row.get("order_id"):
                continue
            if not sku:
                sku = f"ORDER-{row.get('order_id', count)}"
            qty = safe_int(row.get("quantity"), 1)
            price = safe_float(row.get("price") or row.get("unit_price"))
            revenue = safe_float(row.get("revenue")) or (price * qty if price else 0)
            sold_at = pd.to_datetime(row.get("sold_at"), errors="coerce")
            if pd.isna(sold_at):
                sold_at = naive_local_now()
            channel = str(row.get("sales_channel", "")) if pd.notna(row.get("sales_channel")) else None
            customer = str(row.get("customer", "")) if pd.notna(row.get("customer")) else None
            order_id = str(row.get("order_id", "")) if pd.notna(row.get("order_id")) else None
            batch.append(
                SalesRecord(
                    sku=sku,
                    order_id=order_id,
                    quantity=qty,
                    unit_price=price,
                    revenue=revenue,
                    discount_amount=safe_float(row.get("discount_amount")),
                    channel=channel or customer,
                    sold_at=sold_at.to_pydatetime() if hasattr(sold_at, "to_pydatetime") else sold_at,
                    import_id=import_id,
                )
            )
            count += 1
            if len(batch) >= flush_size:
                self.session.add_all(batch)
                await self._flush("sales-batch")
                batch.clear()
        if batch:
            self.session.add_all(batch)
            await self._flush("sales-batch")
        return count



    async def _import_inventory_if_present(self, df: pd.DataFrame, import_id: int) -> int:

        qty_col = None

        for c in ("on_hand", "stock", "quantity", "available_units"):

            if c in df.columns:

                qty_col = c

                break

        if not qty_col and "sku" not in df.columns:

            return 0

        count = 0

        subset = ["sku"] if "sku" in df.columns else None

        rows = df.drop_duplicates(subset=subset) if subset else df

        batch: list[InventoryRecord] = []
        flush_size = self.settings.import_flush_batch_size
        for row in rows.to_dict("records"):
            sku = normalize_sku(str(row.get("sku", ""))) if row.get("sku") is not None else f"INV-{count}"
            if not sku or sku in self._seen_inventory_skus:
                continue
            self._seen_inventory_skus.add(sku)
            qty = safe_int(row.get(qty_col)) if qty_col else 0
            reserved = safe_int(row.get("reserved")) if "reserved" in df.columns else 0
            batch.append(
                InventoryRecord(
                    product_id=0,
                    sku=sku,
                    quantity_on_hand=qty,
                    quantity_reserved=reserved,
                    days_in_stock=safe_int(row.get("days_in_stock"))
                    if pd.notna(row.get("days_in_stock"))
                    else None,
                    import_id=import_id,
                )
            )
            count += 1
            if len(batch) >= flush_size:
                self.session.add_all(batch)
                await self._flush("inventory-batch")
                batch.clear()
        if batch:
            self.session.add_all(batch)
            await self._flush("inventory-batch")
        return count



    async def list_imports(
        self,
        limit: int = 50,
        *,
        organization_id: int | None = None,
        guest_only: bool = False,
    ) -> list[ImportRecord]:
        q = select(ImportRecord).order_by(ImportRecord.started_at.desc()).limit(limit)
        if guest_only:
            q = q.where(ImportRecord.organization_id.is_(None))
        elif organization_id is not None:
            q = q.where(ImportRecord.organization_id == organization_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def delete_import(self, import_id: int, *, remove_upload_copy: bool = True) -> bool:
        """Remove one import and its DB rows. Does not touch data/demo_companies or sample files."""
        from app.models.active_analysis import ActiveAnalysisConfig

        result = await self.session.execute(
            select(ImportRecord).where(ImportRecord.id == import_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False

        await self._clear_import_data(import_id)
        await self.session.execute(delete(ImportRecord).where(ImportRecord.id == import_id))
        await self._clear_active_refs([import_id])

        if remove_upload_copy:
            upload_path = self.settings.upload_dir / record.filename
            if upload_path.is_file():
                try:
                    upload_path.unlink()
                except OSError:
                    pass

        await self._flush("delete-import")
        return True

    async def delete_imports(self, import_ids: list[int]) -> int:
        deleted = 0
        for iid in import_ids:
            if await self.delete_import(iid):
                deleted += 1
        return deleted

    async def _clear_active_refs(self, import_ids: list[int]) -> None:
        from app.models.active_analysis import ActiveAnalysisConfig

        if not import_ids:
            return
        ids_set = set(import_ids)
        result = await self.session.execute(
            select(ActiveAnalysisConfig).where(ActiveAnalysisConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        if not config:
            return
        if config.products_import_id in ids_set:
            config.products_import_id = None
        if config.sales_import_id in ids_set:
            config.sales_import_id = None
        if config.inventory_import_id in ids_set:
            config.inventory_import_id = None


