from pydantic import BaseModel, EmailStr, Field
from app.models.user import RoleEnum

class LoginUserInfo(BaseModel):
    id: int
    email: str
    role: RoleEnum
    full_name: str | None = None
    phone_number: str | None = None
    permissions: list[str] = []

class Token(BaseModel):
    access_token: str
    token_type: str
    user: LoginUserInfo

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum
    full_name: str | None = None
    phone_number: str | None = None

class CandidateRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone_number: str




class UserResponse(BaseModel):
    id: int
    email: str
    role: RoleEnum
    full_name: str | None = None
    phone_number: str | None = None
    institution_id: int | None = None
    permissions: list[str] = []

    class Config:
        from_attributes = True

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters long")
