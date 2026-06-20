"""WooCommerce REST API read-only sync."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.store_connection import StoreConnection
from app.services.import_runner import import_runner
from app.services.import_service import ImportService
from app.utils.app_timezone import naive_local_now
from app.utils.token_vault import decrypt_secret, encrypt_secret

logger = logging.getLogger("commerceflow.woocommerce")


def normalize_store_url(url: str) -> str:
    value = url.strip().rstrip("/")
    if not value.startswith("http"):
        value = f"https://{value}"
    return value


class WooCommerceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_connection(self, organization_id: int) -> StoreConnection | None:
        result = await self.session.execute(
            select(StoreConnection).where(
                StoreConnection.organization_id == organization_id,
                StoreConnection.provider == "woocommerce",
            )
        )
        return result.scalar_one_or_none()

    async def connect(
        self,
        organization_id: int,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
    ) -> StoreConnection:
        base = normalize_store_url(store_url)
        if not consumer_key.strip() or not consumer_secret.strip():
            raise ValueError("WooCommerce consumer key and secret are required.")

        conn = await self.get_connection(organization_id)
        if conn:
            conn.store_domain = base
            conn.api_key_encrypted = encrypt_secret(consumer_key.strip())
            conn.api_secret_encrypted = encrypt_secret(consumer_secret.strip())
            conn.status = "connected"
            conn.updated_at = naive_local_now()
        else:
            conn = StoreConnection(
                organization_id=organization_id,
                provider="woocommerce",
                store_domain=base,
                api_key_encrypted=encrypt_secret(consumer_key.strip()),
                api_secret_encrypted=encrypt_secret(consumer_secret.strip()),
                status="connected",
            )
            self.session.add(conn)
        await self.session.flush()
        return conn

    async def _api_get(self, conn: StoreConnection, path: str, params: dict | None = None) -> list | dict:
        key = decrypt_secret(conn.api_key_encrypted or "")
        secret = decrypt_secret(conn.api_secret_encrypted or "")
        url = urljoin(conn.store_domain + "/", f"wp-json/wc/v3/{path.lstrip('/')}")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, params=params or {}, auth=(key, secret))
            resp.raise_for_status()
            return resp.json()

    async def sync_store(self, organization_id: int) -> dict:
        conn = await self.get_connection(organization_id)
        if not conn or not conn.api_key_encrypted:
            raise ValueError("Connect WooCommerce before syncing.")

        products = await self._api_get(conn, "products", {"per_page": 100})
        orders = await self._api_get(conn, "orders", {"per_page": 100, "status": "any"})

        product_rows = []
        for product in products if isinstance(products, list) else []:
            sku = product.get("sku")
            product_rows.append(
                {
                    "Name": product.get("name"),
                    "SKU": sku,
                    "Regular price": product.get("regular_price"),
                    "Categories": ", ".join(c.get("name", "") for c in product.get("categories", [])),
                }
            )

        sales_rows = []
        for order in orders if isinstance(orders, list) else []:
            for item in order.get("line_items", []):
                sales_rows.append(
                    {
                        "Order ID": order.get("id"),
                        "Quantity": item.get("quantity"),
                        "Order total": item.get("total"),
                        "Date": order.get("date_created"),
                        "Billing Email": order.get("billing", {}).get("email"),
                        "Status": order.get("status"),
                    }
                )

        inventory_rows = []
        for product in products if isinstance(products, list) else []:
            inventory_rows.append(
                {
                    "SKU": product.get("sku"),
                    "Name": product.get("name"),
                    "quantity": product.get("stock_quantity"),
                }
            )

        settings = self.settings
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for label, rows, dataset_type in (
            ("woocommerce_products.xlsx", product_rows, "products"),
            ("woocommerce_sales.xlsx", sales_rows, "sales"),
            ("woocommerce_inventory.xlsx", inventory_rows, "inventory"),
        ):
            if not rows:
                continue
            path = settings.upload_dir / label
            pd.DataFrame(rows).to_excel(path, index=False)
            service = ImportService(self.session)
            record = await service.create_import(
                label,
                "woocommerce",
                dataset_type=dataset_type,
                organization_id=organization_id,
            )
            await self.session.flush()
            await self.session.commit()
            await import_runner.run_import(record.id, path, "woocommerce", forced_type=dataset_type)
            record = await service.get_import(record.id)
            results.append({"filename": label, "status": record.status if record else "unknown"})

        conn.last_sync_at = naive_local_now()
        await self.session.flush()
        return {"synced": results, "store": conn.store_domain}
