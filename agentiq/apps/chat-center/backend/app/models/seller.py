"""Seller model - продавцы с credentials для маркетплейсов"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Seller(Base):
    """Seller model - продавец с подключенным аккаунтом маркетплейса"""

    __tablename__ = "sellers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for legacy records
    marketplace = Column(String(50), nullable=False, default="ozon")

    # Credentials (encrypted)
    client_id = Column(String(255), nullable=True)
    api_key_encrypted = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)  # Email verified
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    sync_status = Column(String(50), nullable=True)  # 'idle', 'syncing', 'error', 'success'
    sync_error = Column(Text, nullable=True)  # Error message if sync failed

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    chats = relationship("Chat", back_populates="seller", cascade="all, delete-orphan")
    sla_rules = relationship("SLARule", back_populates="seller", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Seller(id={self.id}, name='{self.name}', email='{self.email}')>"
