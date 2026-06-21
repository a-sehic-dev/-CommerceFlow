from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.database_url import normalize_async_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommerceFlow"
    product_tagline: str = "Ecommerce Operations Intelligence"
    founder_name: str = "Sedin Šehić"
    founder_url: str = "https://www.linkedin.com/in/sedin-sehic-1134253a8/"
    product_version: str = "1.0.0"
    workspace_mode: str = "demo_workspace"
    auto_bootstrap_demo: bool = True
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-change-in-production"

    database_url: str = "sqlite+aiosqlite:///./data/commerceflow.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_size_mb: int = 50

    analytics_cache_ttl_seconds: int = 300
    low_stock_threshold: int = 10
    # Inventory classification (see app/utils/inventory_classification.py)
    dead_min_days_since_last_sale: int = 180
    dead_max_velocity_90d: float = 0.05
    slow_moving_min_days_since_last_sale: int = 60
    slow_moving_max_days_since_last_sale: int = 179
    slow_moving_max_velocity_90d: float = 0.15
    overstock_min_days_cover: float = 90.0
    overstock_target_days_cover: float = 90.0
    low_stock_max_days_cover: float = 14.0
    margin_warning_pct: float = 15.0

    # Enterprise scale
    db_fetch_chunk_size: int = 25_000
    import_csv_chunk_size: int = 50_000
    import_flush_batch_size: int = 2_000
    sales_aggregate_above_rows: int = 250_000
    analytics_max_detail_rows: int = 500_000
    analytics_issue_cap: int = 500
    fuzzy_duplicate_max_rows: int = 8_000
    export_max_rows_per_sheet: int = 100_000
    ui_table_page_size: int = 50

    # AI assistant
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    assistant_session_limit: int = 8
    assistant_ip_limit: int = 30
    assistant_cooldown_seconds: float = 2.5
    assistant_alert_email: str = "commerceflow.platform@gmail.com"
    usage_stats_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    # Upload abuse protection (Faza 2)
    upload_ip_limit: int = 20
    upload_window_seconds: float = 3600.0
    upload_cooldown_seconds: float = 5.0

    # Public URL for OAuth callbacks (set on Render)
    app_base_url: str = "http://127.0.0.1:8000"

    # Shopify Partner app (Faza 3)
    shopify_api_key: str | None = None
    shopify_api_secret: str | None = None
    shopify_scopes: str = "read_products,read_orders,read_inventory"
    shopify_api_version: str = "2024-10"

    # Team workspaces (Faza 3)
    team_max_seats: int = 5
    invite_token_ttl_hours: int = 72

    # Stripe Billing (Faza 4)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro: str | None = None
    stripe_price_team: str | None = None
    stripe_price_ultra: str | None = None
    stripe_default_currency: str = "usd"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_async_database_url(str(value or ""))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_directories() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)
