from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=256)
    company_name: str = Field(..., min_length=2, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=256)
    password: str = Field(..., min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    organization_id: int
    organization_name: str | None = None
    role: str = "owner"
