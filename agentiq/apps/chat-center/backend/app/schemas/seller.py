"""Seller schemas for API validation"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SellerBase(BaseModel):
    """Base seller schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Seller name")
    marketplace: str = Field(default="ozon", description="Marketplace identifier")
    client_id: Optional[str] = Field(None, description="Ozon Client-Id")
    is_active: bool = Field(default=True, description="Is seller active")


class SellerCreate(SellerBase):
    """Schema for creating new seller"""
    api_key: Optional[str] = Field(None, description="Ozon Api-Key (will be encrypted)")


class SellerUpdate(BaseModel):
    """Schema for updating seller"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_id: Optional[str] = None
    api_key: Optional[str] = Field(None, description="New Api-Key (will be encrypted)")
    is_active: Optional[bool] = None


class SellerResponse(SellerBase):
    """Schema for seller response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SellerListResponse(BaseModel):
    """Schema for sellers list response"""
    sellers: list[SellerResponse]
    total: int
