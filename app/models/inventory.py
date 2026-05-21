from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_in_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    inventory_health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    import_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now)
