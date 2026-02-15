"""Product cache model for WB CDN card data.

Stores product metadata fetched from WB CDN (card.json) with TTL-based refresh.
Used to enrich AI drafts with product context without repeated CDN requests.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func

from app.database import Base


class ProductCache(Base):
    """Product cache for WB CDN card.json data.

    Stores parsed product metadata from WB basket CDN API (no auth required).
    TTL = 24 hours. Upserted on first access or when stale.
    """

    __tablename__ = "product_cache"

    id = Column(Integer, primary_key=True, index=True)
    nm_id = Column(String(50), unique=True, nullable=False, index=True)
    marketplace = Column(String(50), default="wb", nullable=False)

    # Product metadata from card.json
    name = Column(String(500), nullable=True)  # imt_name
    description = Column(Text, nullable=True)  # description
    brand = Column(String(200), nullable=True)  # brand
    category = Column(String(300), nullable=True)  # subj_name

    # Structured data
    options = Column(JSON, nullable=True)  # options array (размер, цвет, состав...)
    image_url = Column(String(500), nullable=True)  # первая картинка

    # Cache metadata
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<ProductCache(nm_id='{self.nm_id}', name='{self.name}')>"
