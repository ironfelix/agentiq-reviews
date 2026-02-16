"""Leads API endpoints - заявки с лендинга"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.database import get_db
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new lead from landing form.

    Public endpoint (no auth required) - accepts form data from landing page.
    """
    try:
        # Check if lead with same nm + contact already exists (dedup)
        existing = await db.execute(
            select(Lead).where(
                Lead.nm == lead_data.nm,
                Lead.contact == lead_data.contact
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Заявка с таким артикулом и контактом уже существует"
            )

        # Create new lead
        lead = Lead(
            nm=lead_data.nm,
            contact=lead_data.contact,
            company=lead_data.company,
            wblink=lead_data.wblink,
            status="new",
            source="landing"
        )

        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        logger.info(f"New lead created: id={lead.id}, nm={lead.nm}, contact={lead.contact}")

        return LeadResponse.model_validate(lead)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating lead: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при сохранении заявки"
        )
