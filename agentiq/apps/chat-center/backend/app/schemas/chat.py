"""Chat schemas for API validation"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ChatBase(BaseModel):
    """Base chat schema"""
    marketplace: str = Field(..., description="Marketplace identifier (ozon/wb)")
    marketplace_chat_id: str = Field(..., description="External chat ID from marketplace")
    order_id: Optional[str] = Field(None, description="Related order ID")
    product_id: Optional[str] = Field(None, description="Related product ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_id: Optional[str] = Field(None, description="Customer external ID")


class ChatResponse(ChatBase):
    """Schema for chat response"""
    id: int
    seller_id: int
    status: str = Field(..., description="Chat status (open/closed)")
    unread_count: int = Field(0, description="Number of unread messages")
    last_message_at: Optional[datetime] = Field(None, description="Timestamp of last message")
    first_message_at: Optional[datetime] = Field(None, description="Timestamp of first message")
    sla_deadline_at: Optional[datetime] = Field(None, description="SLA deadline")
    sla_priority: str = Field("normal", description="SLA priority (low/normal/high/urgent)")
    ai_suggestion_text: Optional[str] = Field(None, description="AI generated suggestion text")
    ai_analysis_json: Optional[str] = Field(None, description="AI analysis JSON string")
    last_message_preview: Optional[str] = Field(None, description="Preview of last message")
    product_name: Optional[str] = Field(None, description="Product name")
    product_article: Optional[str] = Field(None, description="Product article/SKU")
    chat_status: Optional[str] = Field("waiting", description="Chat workflow status")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """Schema for chats list response"""
    chats: list[ChatResponse]
    total: int
    page: int = Field(1, description="Current page number")
    page_size: int = Field(50, description="Items per page")


class ChatFilter(BaseModel):
    """Schema for chat filtering"""
    seller_id: Optional[int] = None
    status: Optional[str] = Field(None, description="Filter by status (open/closed)")
    marketplace: Optional[str] = Field(None, description="Filter by marketplace")
    unread_only: bool = Field(False, description="Show only unread chats")
    sla_overdue_only: bool = Field(False, description="Show only SLA overdue chats")
    search: Optional[str] = Field(None, description="Search in customer name or order_id")
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)
