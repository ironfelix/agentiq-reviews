"""Auth schemas for API validation"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    """Schema for user registration"""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    name: str = Field(..., min_length=1, max_length=255, description="Seller/Company name")
    marketplace: str = Field(default="wildberries", description="Primary marketplace")


class LoginRequest(BaseModel):
    """Schema for user login"""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class AuthResponse(BaseModel):
    """Schema for auth response with user info"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    seller: "SellerAuthInfo"


class SellerAuthInfo(BaseModel):
    """Seller info in auth response"""
    id: int
    email: str
    name: str
    marketplace: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """Schema for password change"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ConnectMarketplaceRequest(BaseModel):
    """Schema for connecting marketplace API"""
    api_key: str = Field(..., min_length=10, description="Wildberries API key")
    client_id: Optional[str] = Field(None, description="Optional client ID")


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    email: EmailStr = Field(..., description="Email address")


class MeResponse(BaseModel):
    """Schema for /me endpoint"""
    id: int
    email: str
    name: str
    marketplace: str
    is_active: bool
    is_verified: bool
    has_api_credentials: bool
    last_sync_at: Optional[datetime]
    sync_status: Optional[str] = None  # 'idle', 'syncing', 'error', 'success'
    sync_error: Optional[str] = None  # Error message if sync failed
    created_at: datetime

    class Config:
        from_attributes = True


# Update forward reference
AuthResponse.model_rebuild()
