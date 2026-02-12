"""Sellers API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import logging

from app.database import get_db
from app.models.seller import Seller
from app.schemas.seller import (
    SellerCreate,
    SellerUpdate,
    SellerResponse,
    SellerListResponse
)
from app.services.encryption import encrypt_credentials

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("", response_model=SellerListResponse)
async def list_sellers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get list of all sellers"""
    # Count total
    count_result = await db.execute(select(func.count(Seller.id)))
    total = count_result.scalar_one()

    # Get sellers
    result = await db.execute(
        select(Seller)
        .order_by(Seller.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    sellers = result.scalars().all()

    return SellerListResponse(
        sellers=[SellerResponse.model_validate(s) for s in sellers],
        total=total
    )


@router.get("/{seller_id}", response_model=SellerResponse)
async def get_seller(
    seller_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get seller by ID"""
    result = await db.execute(
        select(Seller).where(Seller.id == seller_id)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller {seller_id} not found"
        )

    return SellerResponse.model_validate(seller)


@router.post("", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
async def create_seller(
    seller_data: SellerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new seller"""
    # Encrypt API key if provided
    api_key_encrypted = None
    if seller_data.api_key:
        api_key_encrypted = encrypt_credentials(seller_data.api_key)

    seller = Seller(
        name=seller_data.name,
        marketplace=seller_data.marketplace,
        client_id=seller_data.client_id,
        api_key_encrypted=api_key_encrypted,
        is_active=seller_data.is_active
    )

    db.add(seller)
    await db.commit()
    await db.refresh(seller)

    logger.info(f"Created seller: {seller.id} ({seller.name})")
    return SellerResponse.model_validate(seller)


@router.patch("/{seller_id}", response_model=SellerResponse)
async def update_seller(
    seller_id: int,
    seller_data: SellerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update seller"""
    result = await db.execute(
        select(Seller).where(Seller.id == seller_id)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller {seller_id} not found"
        )

    # Update fields
    update_data = seller_data.model_dump(exclude_unset=True)

    # Handle API key encryption
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key_encrypted"] = encrypt_credentials(update_data.pop("api_key"))
    elif "api_key" in update_data:
        update_data.pop("api_key")

    for field, value in update_data.items():
        setattr(seller, field, value)

    await db.commit()
    await db.refresh(seller)

    logger.info(f"Updated seller: {seller.id}")
    return SellerResponse.model_validate(seller)


@router.delete("/{seller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seller(
    seller_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete seller (soft delete by deactivating)"""
    result = await db.execute(
        select(Seller).where(Seller.id == seller_id)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller {seller_id} not found"
        )

    seller.is_active = False
    await db.commit()

    logger.info(f"Deactivated seller: {seller.id}")
    return None
