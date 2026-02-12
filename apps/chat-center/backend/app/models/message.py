"""Message model - сообщения в чатах"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Message(Base):
    """Message model - сообщение в чате (incoming от покупателя или outgoing от продавца)"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)

    # External ID
    external_message_id = Column(String(255), nullable=False)

    # Direction & Content
    direction = Column(String(20), nullable=False)  # 'incoming' or 'outgoing'
    text = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)  # [{"type": "image", "url": "...", "file_name": "..."}]

    # Author (для incoming)
    author_type = Column(String(20), nullable=True)  # 'customer', 'seller', 'system'
    author_id = Column(String(100), nullable=True)

    # Status
    status = Column(String(20), default="sent", nullable=False)  # 'pending', 'sent', 'delivered', 'read', 'failed'
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    sent_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    chat = relationship("Chat", back_populates="messages")

    # Constraints
    __table_args__ = (
        UniqueConstraint("chat_id", "external_message_id", name="uq_message_chat_external"),
        Index("idx_messages_chat", "chat_id", "sent_at"),
        Index("idx_messages_unread", "is_read", "sent_at"),
        Index("idx_messages_status", "status"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, chat_id={self.chat_id}, direction='{self.direction}', status='{self.status}')>"
