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
        """Validate contact - must be telegram, phone or email"""
        v = v.strip()
        if not v:
            raise ValueError('Контакт обязателен')

        # Check if it's a telegram handle (@username)
        if v.startswith('@'):
            if len(v) < 2:
                raise ValueError('Telegram handle должен содержать хотя бы 1 символ после @')
            return v

        # Check if it's a phone (starts with + or digit)
        if v[0] in ['+', '7', '8'] or v[0].isdigit():
            # Remove spaces, dashes, parentheses
            phone_clean = re.sub(r'[\s\-\(\)]', '', v)
            if len(phone_clean) < 10:
                raise ValueError('Номер телефона слишком короткий')
            return v

        # Check if it's an email
        if '@' in v and '.' in v:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError('Некорректный email')
            return v

        # If it looks like a telegram username (letters, digits, underscores), add @ automatically
        if re.match(r'^[a-zA-Z0-9_]+$', v):
            if len(v) >= 1:
                return f'@{v}'
            raise ValueError('Telegram username слишком короткий')

        raise ValueError('Контакт должен быть telegram (username или @username), телефон или email')


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
