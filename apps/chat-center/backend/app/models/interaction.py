"""Interaction model - unified communication entity across channels."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Interaction(Base):
    """Unified interaction entity for reviews, questions, and chats."""

    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace = Column(String(50), nullable=False, default="wb")

    # Channel identity
    channel = Column(String(20), nullable=False)  # review | question | chat
    external_id = Column(String(255), nullable=False)

    # Optional cross-channel correlation keys
    customer_id = Column(String(100), nullable=True)
    order_id = Column(String(100), nullable=True)
    nm_id = Column(String(100), nullable=True)
    product_article = Column(String(100), nullable=True)

    # Interaction content
    subject = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # For review channel

    # Workflow state
    status = Column(String(50), nullable=False, default="open")
    priority = Column(String(20), nullable=False, default="normal")
    needs_response = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=False, default="wb_api")  # wb_api | wbcon_fallback

    # Event timeline
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Channel-specific raw details for audit/debug
    extra_data = Column("metadata", JSON, nullable=True)

    # Relationships
    seller = relationship("Seller", back_populates="interactions")
    events = relationship("InteractionEvent", back_populates="interaction", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "seller_id",
            "marketplace",
            "channel",
            "external_id",
            name="uq_interactions_identity",
        ),
        Index("idx_interactions_channel_status", "seller_id", "channel", "status"),
        Index("idx_interactions_priority", "seller_id", "priority", "needs_response"),
        Index("idx_interactions_occurred", "seller_id", "occurred_at"),
        Index("idx_interactions_source", "seller_id", "source"),
    )

    def __repr__(self):
        return (
            f"<Interaction(id={self.id}, seller_id={self.seller_id}, "
            f"channel='{self.channel}', status='{self.status}')>"
        )
