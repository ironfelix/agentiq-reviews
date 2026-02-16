"""Lead model - заявки с лендинга"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class Lead(Base):
    """Lead model - заявка на аудит с лендинга"""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    # Form data
    nm = Column(String(50), nullable=False)  # Артикул WB
    contact = Column(String(255), nullable=False)  # Telegram/phone/email
    company = Column(String(255), nullable=True)  # Название магазина (опционально)
    wblink = Column(String(500), nullable=True)  # Ссылка на товар WB (опционально)

    # Status tracking
    status = Column(String(50), nullable=False, default="new", index=True)  # new, contacted, converted, rejected
    notes = Column(Text, nullable=True)  # Заметки менеджера

    # Metadata
    source = Column(String(50), nullable=False, default="landing")  # landing, chat, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes for filtering and sorting
    __table_args__ = (
        Index('idx_leads_status_created', 'status', 'created_at'),
    )

    def __repr__(self):
        return f"<Lead(id={self.id}, nm='{self.nm}', contact='{self.contact}', status='{self.status}')>"
