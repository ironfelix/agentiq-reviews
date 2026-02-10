"""Message schemas for API validation"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AttachmentSchema(BaseModel):
    """Schema for message attachment"""
    type: str = Field(..., description="Attachment type (image/file)")
    url: Optional[str] = Field(None, description="Attachment URL")
    file_name: Optional[str] = Field(None, description="File name")


class MessageBase(BaseModel):
    """Base message schema"""
    text: Optional[str] = Field(None, description="Message text content")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Message attachments")


class MessageCreate(MessageBase):
    """Schema for creating new message (sending)"""
    chat_id: int = Field(..., description="Chat ID to send message to")


class MessageResponse(MessageBase):
    """Schema for message response"""
    id: int
    chat_id: int
    external_message_id: str = Field(..., description="External message ID from marketplace")
    direction: str = Field(..., description="Message direction (incoming/outgoing)")
    author_type: Optional[str] = Field(None, description="Author type (customer/seller/system)")
    author_id: Optional[str] = Field(None, description="Author external ID")
    status: str = Field(..., description="Message status (pending/sent/delivered/read/failed)")
    is_read: bool = Field(False, description="Is message read")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    sent_at: datetime = Field(..., description="Message sent timestamp")
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Schema for messages list response"""
    messages: list[MessageResponse]
    total: int
