import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, description="User full name")
    email: EmailStr
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    organization_name: str = Field(..., min_length=1, description="Organization name")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class OrganizationOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    organization_id: int
    name: str
    email: EmailStr
    role: str
    organization: Optional[OrganizationOut] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
