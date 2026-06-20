from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class StoreConnection(Base):
    __tablename__ = "store_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)  # shopify | woocommerce
    store_domain: Mapped[str] = mapped_column(String(512))
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="connected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now, onupdate=naive_local_now)
