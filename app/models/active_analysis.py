from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class ActiveAnalysisConfig(Base):
    """Singleton row storing explicitly selected import datasets for analysis."""

    __tablename__ = "active_analysis_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    products_import_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_import_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_import_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now, onupdate=naive_local_now)
