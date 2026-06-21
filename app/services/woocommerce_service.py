"""WooCommerce REST API read-only sync."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.store_connection import StoreConnection
from app.services.import_runner import import_runner
from app.services.import_service import ImportService
from app.services.plan_service import PlanService
from app.services.store_connection_service import StoreConnectionService, store_slug
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
        self.stores = StoreConnectionService(session)
        self.plans = PlanService(session)

    async def list_connections(self, organization_id: int) -> list[StoreConnection]:
        return await self.stores.list_connections(organization_id, provider="woocommerce")

    async def get_connection(self, organization_id: int) -> StoreConnection | None:
        connections = await self.list_connections(organization_id)
        return connections[0] if connections else None

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

        conn = await self.stores.get_by_domain(organization_id, "woocommerce", base)
        if not conn:
            used = await self.stores.connected_count(organization_id)
            limits = await self.plans.ensure_live_sync(organization_id)
            if used >= limits.max_stores:
                raise ValueError(
                    f"Store limit reached ({limits.max_stores} on {limits.label}). "
                    "Upgrade to Ultra for multiple stores."
                )
            conn = StoreConnection(
                organization_id=organization_id,
                provider="woocommerce",
                store_domain=base,
                api_key_encrypted=encrypt_secret(consumer_key.strip()),
                api_secret_encrypted=encrypt_secret(consumer_secret.strip()),
                status="connected",
            )
            self.session.add(conn)
        else:
            conn.api_key_encrypted = encrypt_secret(consumer_key.strip())
            conn.api_secret_encrypted = encrypt_secret(consumer_secret.strip())
            conn.status = "connected"
            conn.updated_at = naive_local_now()
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

    async def _sync_connection(self, conn: StoreConnection, organization_id: int) -> list[dict]:
        products = await self._api_get(conn, "products", {"per_page": 100})
        orders = await self._api_get(conn, "orders", {"per_page": 100, "status": "any"})

        product_rows = []
        for product in products if isinstance(products, list) else []:
            product_rows.append(
                {
                    "Name": product.get("name"),
                    "SKU": product.get("sku"),
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

        slug = store_slug(conn.store_domain)
        settings = self.settings
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for label, rows, dataset_type in (
            (f"woocommerce_{slug}_products.xlsx", product_rows, "products"),
            (f"woocommerce_{slug}_sales.xlsx", sales_rows, "sales"),
            (f"woocommerce_{slug}_inventory.xlsx", inventory_rows, "inventory"),
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
            results.append(
                {
                    "filename": label,
                    "status": record.status if record else "unknown",
                    "store": conn.store_domain,
                }
            )

        conn.last_sync_at = naive_local_now()
        await self.session.flush()
        return results

    async def sync_store(self, organization_id: int) -> dict:
        await self.plans.ensure_live_sync(organization_id)
        connections = [
            c for c in await self.list_connections(organization_id) if c.api_key_encrypted
        ]
        if not connections:
            raise ValueError("Connect WooCommerce before syncing.")

        all_synced: list[dict] = []
        for conn in connections:
            all_synced.extend(await self._sync_connection(conn, organization_id))
        return {
            "synced": all_synced,
            "stores": [c.store_domain for c in connections],
        }
