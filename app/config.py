from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommerceFlow"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-change-in-production"

    database_url: str = "sqlite+aiosqlite:///./data/commerceflow.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_size_mb: int = 50

    analytics_cache_ttl_seconds: int = 300
    low_stock_threshold: int = 10
    overstock_days: int = 90
    dead_inventory_days: int = 120
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
