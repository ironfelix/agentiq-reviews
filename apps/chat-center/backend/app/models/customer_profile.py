"""Customer profile model for cross-interaction aggregation."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Float,
    Boolean,
    JSON,
)
from sqlalchemy.sql import func

from app.database import Base


class CustomerProfile(Base):
    """Customer profile with aggregated interaction history."""

    __tablename__ = "customer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    marketplace = Column(String(50), nullable=False, default="wb")

    # Identity (best known)
    customer_id = Column(String(100), nullable=True, index=True)  # WB customer_id if available
    name = Column(String(300), nullable=True)  # Extracted from interactions

    # Aggregates (updated on each interaction)
    total_interactions = Column(Integer, default=0)
    total_reviews = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    total_chats = Column(Integer, default=0)
    avg_rating = Column(Float, nullable=True)  # Average review rating
    last_interaction_at = Column(DateTime(timezone=True))
    first_interaction_at = Column(DateTime(timezone=True))

    # Sentiment trend
    sentiment_trend = Column(String(20), default="neutral")  # improving | stable | declining | neutral
    recent_sentiment_scores = Column(JSON, default=list)  # last 5 sentiment scores

    # Flags
    is_repeat_complainer = Column(Boolean, default=False)  # 3+ negative interactions
    is_vip = Column(Boolean, default=False)  # high order count or positive history

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("seller_id", "marketplace", "customer_id", name="uq_customer_profile"),
        Index("idx_customer_profiles_seller", "seller_id", "marketplace"),
    )

    def __repr__(self):
        return (
            f"<CustomerProfile(id={self.id}, seller_id={self.seller_id}, "
            f"customer_id='{self.customer_id}', total_interactions={self.total_interactions})>"
        )
