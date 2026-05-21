from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    normalized_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    vendor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    compare_at_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    performance_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_indicator: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    import_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=naive_local_now, onupdate=naive_local_now
    )
