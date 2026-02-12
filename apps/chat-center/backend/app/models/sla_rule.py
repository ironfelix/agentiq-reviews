"""SLA Rule model - правила SLA для автоматического расчета deadlines"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SLARule(Base):
    """SLA Rule model - правило SLA для автоматического расчета deadline"""

    __tablename__ = "sla_rules"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)

    # Rule config
    name = Column(String(255), nullable=False)
    condition_type = Column(String(50), nullable=False)  # 'keyword', 'chat_type', 'rating', 'time_based'
    condition_value = Column(Text, nullable=True)  # JSON or string (e.g., "брак|возврат|дефект")
    deadline_minutes = Column(Integer, nullable=False)  # SLA deadline в минутах
    priority = Column(Integer, default=100, nullable=False)  # Higher = more priority (evaluated first)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    seller = relationship("Seller", back_populates="sla_rules")

    # Indexes
    __table_args__ = (
        Index("idx_sla_rules_seller", "seller_id", "is_active"),
        Index("idx_sla_rules_priority", "priority"),
    )

    def __repr__(self):
        return f"<SLARule(id={self.id}, name='{self.name}', condition_type='{self.condition_type}', deadline={self.deadline_minutes}m)>"
