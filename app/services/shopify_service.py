"""Shopify Admin API OAuth and read-only sync."""

from __future__ import annotations

import hashlib
import hmac
import logging
from urllib.parse import urlencode

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

logger = logging.getLogger("commerceflow.shopify")


def normalize_shop_domain(shop: str) -> str:
    value = shop.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not value:
        raise ValueError("Enter your Shopify store domain.")
    if "." not in value:
        value = f"{value}.myshopify.com"
    if not value.endswith(".myshopify.com"):
        raise ValueError("Use your myshopify.com store domain (e.g. acme.myshopify.com).")
    return value


class ShopifyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.stores = StoreConnectionService(session)
        self.plans = PlanService(session)

    def _configured(self) -> None:
        if not self.settings.shopify_api_key or not self.settings.shopify_api_secret:
            raise ValueError("Shopify app credentials are not configured on the server.")

    def authorize_url(self, shop: str, state: str) -> str:
        self._configured()
        domain = normalize_shop_domain(shop)
        params = {
            "client_id": self.settings.shopify_api_key,
            "scope": self.settings.shopify_scopes,
            "redirect_uri": f"{self.settings.app_base_url.rstrip('/')}/api/integrations/shopify/callback",
            "state": state,
        }
        return f"https://{domain}/admin/oauth/authorize?{urlencode(params)}"

    def verify_hmac(self, query_params: dict[str, str]) -> bool:
        self._configured()
        received = query_params.get("hmac", "")
        items = sorted((k, v) for k, v in query_params.items() if k not in {"hmac", "signature"})
        message = "&".join(f"{k}={v}" for k, v in items)
        digest = hmac.new(
            self.settings.shopify_api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, received)

    async def exchange_token(self, shop: str, code: str) -> str:
        self._configured()
        domain = normalize_shop_domain(shop)
        url = f"https://{domain}/admin/oauth/access_token"
        payload = {
            "client_id": self.settings.shopify_api_key,
            "client_secret": self.settings.shopify_api_secret,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        token = data.get("access_token")
        if not token:
            raise ValueError("Shopify did not return an access token.")
        return token

    async def list_connections(self, organization_id: int) -> list[StoreConnection]:
        return await self.stores.list_connections(organization_id, provider="shopify")

    async def get_connection(self, organization_id: int) -> StoreConnection | None:
        connections = await self.list_connections(organization_id)
        return connections[0] if connections else None

    async def save_connection(self, organization_id: int, shop: str, access_token: str) -> StoreConnection:
        domain = normalize_shop_domain(shop)
        conn = await self.stores.get_by_domain(organization_id, "shopify", domain)
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
                provider="shopify",
                store_domain=domain,
                access_token_encrypted=encrypt_secret(access_token),
                scopes=self.settings.shopify_scopes,
                status="connected",
            )
            self.session.add(conn)
        else:
            conn.access_token_encrypted = encrypt_secret(access_token)
            conn.scopes = self.settings.shopify_scopes
            conn.status = "connected"
            conn.updated_at = naive_local_now()
        await self.session.flush()
        return conn

    async def _api_get(self, conn: StoreConnection, path: str) -> dict:
        token = decrypt_secret(conn.access_token_encrypted or "")
        version = self.settings.shopify_api_version
        url = f"https://{conn.store_domain}/admin/api/{version}/{path.lstrip('/')}"
        headers = {"X-Shopify-Access-Token": token}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _sync_connection(self, conn: StoreConnection, organization_id: int) -> list[dict]:
        products_payload = await self._api_get(conn, "products.json?limit=250")
        orders_payload = await self._api_get(conn, "orders.json?status=any&limit=250")

        product_rows = []
        for product in products_payload.get("products", []):
            for variant in product.get("variants", []):
                product_rows.append(
                    {
                        "Title": product.get("title"),
                        "Variant SKU": variant.get("sku"),
                        "Variant Price": variant.get("price"),
                        "Vendor": product.get("vendor"),
                        "Product Category": product.get("product_type"),
                        "Cost per item": variant.get("inventory_item_id"),
                    }
                )

        sales_rows = []
        for order in orders_payload.get("orders", []):
            for item in order.get("line_items", []):
                sales_rows.append(
                    {
                        "Name": order.get("name"),
                        "Lineitem quantity": item.get("quantity"),
                        "Total": item.get("price"),
                        "Created at": order.get("created_at"),
                        "Email": order.get("email"),
                        "Source": order.get("source_name"),
                        "Status": order.get("financial_status"),
                    }
                )

        inventory_rows = []
        for product in products_payload.get("products", []):
            for variant in product.get("variants", []):
                inventory_rows.append(
                    {
                        "SKU": variant.get("sku"),
                        "Title": product.get("title"),
                        "quantity": variant.get("inventory_quantity"),
                    }
                )

        slug = store_slug(conn.store_domain)
        settings = self.settings
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for label, rows, dataset_type in (
            (f"shopify_{slug}_products.xlsx", product_rows, "products"),
            (f"shopify_{slug}_sales.xlsx", sales_rows, "sales"),
            (f"shopify_{slug}_inventory.xlsx", inventory_rows, "inventory"),
        ):
            if not rows:
                continue
            path = settings.upload_dir / label
            pd.DataFrame(rows).to_excel(path, index=False)
            service = ImportService(self.session)
            record = await service.create_import(
                label,
                "shopify",
                dataset_type=dataset_type,
                organization_id=organization_id,
            )
            await self.session.flush()
            await self.session.commit()
            await import_runner.run_import(record.id, path, "shopify", forced_type=dataset_type)
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
            c for c in await self.list_connections(organization_id) if c.access_token_encrypted
        ]
        if not connections:
            raise ValueError("Connect Shopify before syncing.")

        all_synced: list[dict] = []
        for conn in connections:
            all_synced.extend(await self._sync_connection(conn, organization_id))
        return {
            "synced": all_synced,
            "stores": [c.store_domain for c in connections],
        }
