"""Chat model - чаты с покупателями"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Chat(Base):
    """Chat model - чат с покупателем (unified для всех маркетплейсов)"""

    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    marketplace = Column(String(50), nullable=False)

    # External IDs
    marketplace_chat_id = Column(String(255), nullable=False)
    order_id = Column(String(100), nullable=True)
    product_id = Column(String(100), nullable=True)

    # Customer info
    customer_name = Column(String(255), nullable=True)
    customer_id = Column(String(100), nullable=True)

    # Chat status
    status = Column(String(50), default="open", nullable=False)
    unread_count = Column(Integer, default=0, nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    first_message_at = Column(DateTime(timezone=True), nullable=True)

    # SLA
    sla_deadline_at = Column(DateTime(timezone=True), nullable=True)
    sla_priority = Column(String(20), default="normal", nullable=False)

    # Extra data (flexible field for marketplace-specific data)
    extra_data = Column("metadata", JSON, nullable=True)

    # AI fields
    ai_suggestion_text = Column(String, nullable=True)
    ai_analysis_json = Column(String, nullable=True)
    last_message_preview = Column(String(500), nullable=True)
    product_name = Column(String(255), nullable=True)
    product_article = Column(String(100), nullable=True)
    chat_status = Column(String(50), default="waiting", nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    seller = relationship("Seller", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.sent_at")

    # Constraints
    __table_args__ = (
        UniqueConstraint("seller_id", "marketplace_chat_id", name="uq_chat_seller_marketplace"),
        Index("idx_chats_seller_status", "seller_id", "status", "last_message_at"),
        Index("idx_chats_unread", "seller_id", "unread_count"),
        Index("idx_chats_sla", "sla_deadline_at"),
        Index("idx_chats_updated", "updated_at"),
    )

    def __repr__(self):
        return f"<Chat(id={self.id}, marketplace='{self.marketplace}', customer='{self.customer_name}', status='{self.status}')>"
