"""Runtime key-value settings stored in DB."""

from sqlalchemy import Column, DateTime, Integer, String, Text, Index
from sqlalchemy.sql import func

from app.database import Base


class RuntimeSetting(Base):
    """Generic runtime setting for operational toggles/configs."""

    __tablename__ = "runtime_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_runtime_settings_key", "key"),
    )

    def __repr__(self):
        return f"<RuntimeSetting(key='{self.key}')>"
