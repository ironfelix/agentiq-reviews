"""Interaction event model for quality and funnel metrics."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class InteractionEvent(Base):
    """Atomic event in interaction lifecycle (draft/reply/etc)."""

    __tablename__ = "interaction_events"

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(
        Integer,
        ForeignKey("interactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    interaction = relationship("Interaction", back_populates="events")
    seller = relationship("Seller")

    __table_args__ = (
        Index("idx_interaction_events_seller_created", "seller_id", "created_at"),
        Index("idx_interaction_events_channel_type", "channel", "event_type"),
    )

