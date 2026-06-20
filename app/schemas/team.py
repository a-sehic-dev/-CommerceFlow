from pydantic import BaseModel, Field


class AcceptInviteRequest(BaseModel):
    invite_token: str = Field(..., min_length=16, max_length=128)
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=256)
