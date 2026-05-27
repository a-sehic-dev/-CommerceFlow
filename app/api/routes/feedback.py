from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feedback import FeedbackEntry

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_text: str | None = Field(default=None, max_length=2000)
    email_optional: str | None = Field(default=None, max_length=320)
    session_id: str = Field(..., min_length=8, max_length=120)
    most_useful: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("feedback_text")
    @classmethod
    def clean_feedback(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("email_optional")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address or leave it blank.")
        return value

    @field_validator("most_useful")
    @classmethod
    def keep_known_options(cls, value: list[str]) -> list[str]:
        allowed = {
            "Inventory intelligence",
            "KPI dashboards",
            "Profit leakage detection",
            "Reporting exports",
            "Alerts & recommendations",
        }
        return [item for item in value if item in allowed]


@router.post("")
async def create_feedback(body: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    entry = FeedbackEntry(
        rating=body.rating,
        feedback_text=body.feedback_text,
        email_optional=body.email_optional,
        session_id=body.session_id,
        most_useful=", ".join(body.most_useful) if body.most_useful else None,
    )
    db.add(entry)
    await db.flush()
    return {
        "success": True,
        "id": entry.id,
        "testimonial_prompt": body.rating >= 4,
        "message": "Feedback captured. Thank you for helping improve CommerceFlow.",
    }
