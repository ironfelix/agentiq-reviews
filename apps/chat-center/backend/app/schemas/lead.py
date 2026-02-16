"""Lead schemas - валидация заявок"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
import re


class LeadCreate(BaseModel):
    """Schema for creating a lead from landing form"""

    nm: str = Field(..., min_length=1, max_length=50, description="Артикул WB")
    contact: str = Field(..., min_length=3, max_length=255, description="Telegram/phone/email")
    company: Optional[str] = Field(None, max_length=255, description="Название магазина")
    wblink: Optional[str] = Field(None, max_length=500, description="Ссылка на товар WB")

    @field_validator('nm')
    @classmethod
    def validate_nm(cls, v: str) -> str:
        """Validate WB article number"""
        v = v.strip()
        if not v.isdigit():
            raise ValueError('Артикул должен содержать только цифры')
        return v

    @field_validator('contact')
    @classmethod
    def validate_contact(cls, v: str) -> str:
        """Validate contact - minimal validation, just ensure it's not empty"""
        v = v.strip()
        if not v:
            raise ValueError('Контакт обязателен')

        if len(v) < 2:
            raise ValueError('Контакт слишком короткий (минимум 2 символа)')

        # Auto-add @ for telegram usernames (letters only at start, no digits at start to avoid phone confusion)
        # Only if it looks clearly like a username (starts with letter, only letters/digits/_)
        if v[0].isalpha() and re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            return f'@{v}'

        # Return as-is for everything else (phone, email, telegram with @, or any other format)
        return v


class LeadResponse(BaseModel):
    """Schema for lead response"""

    id: int
    nm: str
    contact: str
    company: Optional[str]
    wblink: Optional[str]
    status: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    """Schema for updating lead status"""

    status: Optional[str] = Field(None, pattern=r'^(new|contacted|converted|rejected)$')
    notes: Optional[str] = Field(None, max_length=2000)
