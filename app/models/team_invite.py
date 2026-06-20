from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.app_timezone import naive_local_now


class TeamInvite(Base):
    __tablename__ = "team_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    email: Mapped[str] = mapped_column(String(256), index=True)
    role: Mapped[str] = mapped_column(String(32), default="analyst")
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_local_now)
