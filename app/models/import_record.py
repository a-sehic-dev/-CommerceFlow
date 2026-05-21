from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class ImportRecord(Base):
    __tablename__ = "import_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512))
    source_type: Mapped[str] = mapped_column(String(64))
    dataset_type: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detection_scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_type_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    products_imported: Mapped[int] = mapped_column(Integer, default=0)
    sales_imported: Mapped[int] = mapped_column(Integer, default=0)
    inventory_imported: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
