"""Interactions API endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_seller, require_seller_ownership
from app.models.chat import Chat
from app.models.interaction import Interaction
from app.models.message import Message
from app.models.seller import Seller
from app.schemas.interaction import (
    InteractionChannelQuality,
    InteractionChannelPipeline,
    InteractionDraftRequest,
    InteractionDraftResponse,
    InteractionListResponse,
    InteractionPipelineMetrics,
    InteractionQualityHistoryPoint,
    InteractionQualityHistoryResponse,
    InteractionQualityMetricsResponse,
    InteractionQualityTotals,
    InteractionReplyRequest,
    InteractionReplyResponse,
    InteractionResponse,
    InteractionSyncResponse,
    InteractionOpsAlert,
    InteractionOpsAlertsResponse,
    InteractionPilotReadinessCheck,
    InteractionPilotReadinessResponse,
    InteractionPilotReadinessSummary,
    InteractionTimelineResponse,
    InteractionTimelineStep,
)
from app.services.interaction_ingest import ingest_wb_reviews_to_interactions
from app.services.interaction_ingest import ingest_wb_questions_to_interactions
from app.services.interaction_ingest import ingest_chat_interactions
from app.services.guardrails import validate_reply_text
from app.services.interaction_drafts import generate_interaction_draft
from app.services.interaction_linking import get_deterministic_thread_timeline
from app.services.interaction_metrics import (
    get_pilot_readiness,
    get_ops_alerts,
    get_quality_history,
    get_quality_metrics,
    record_draft_event,
    record_reply_events,
)
from app.schemas.analytics import RevenueImpactResponse
from app.services.revenue_analytics import get_revenue_impact
from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller
from app.services.wb_questions_connector import get_wb_questions_connector_for_seller
from app.services.celery_health import get_celery_health

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.get("", response_model=InteractionListResponse)
async def list_interactions(
    channel: Optional[str] = Query(None, description="Filter by channel: review/question/chat"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    needs_response: Optional[bool] = Query(None, description="Filter by response requirement"),
    marketplace: Optional[str] = Query(None, description="Filter by marketplace"),
    source: Optional[str] = Query(None, description="Filter by data source"),
    search: Optional[str] = Query(None, description="Search by text/product/customer/order"),
    include_total: bool = Query(True, description="Include total count (can be slow for large datasets)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Get unified interactions list.
    """
    offset = (page - 1) * page_size

    query = select(Interaction)
    conditions = []

    conditions.append(Interaction.seller_id == current_seller.id)
    if channel:
        conditions.append(Interaction.channel == channel)
    if status_filter:
        conditions.append(Interaction.status == status_filter)
    if priority:
        conditions.append(Interaction.priority == priority)
    if needs_response is not None:
        conditions.append(Interaction.needs_response == needs_response)
    if marketplace:
        conditions.append(Interaction.marketplace == marketplace)
    if source:
        conditions.append(Interaction.source == source)
    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                Interaction.text.ilike(search_term),
                Interaction.subject.ilike(search_term),
                Interaction.product_article.ilike(search_term),
                Interaction.nm_id.ilike(search_term),
                Interaction.customer_id.ilike(search_term),
                Interaction.order_id.ilike(search_term),
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    total = 0
    if include_total:
        # Avoid counting from a "select *" subquery: SQLite/Postgres can plan it poorly.
        count_query = select(func.count(Interaction.id)).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total = int(count_result.scalar_one() or 0)

    query = (
        query.order_by(Interaction.occurred_at.desc().nullslast(), Interaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return InteractionListResponse(
        interactions=[InteractionResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/sync/reviews", response_model=InteractionSyncResponse)
async def sync_reviews(
    nm_id: Optional[int] = Query(None, ge=1, description="Filter sync by WB nmId"),
    only_unanswered: bool = Query(False, description="Sync only unanswered reviews"),
    max_items: int = Query(300, ge=1, le=5000, description="Max reviews to ingest"),
    page_size: int = Query(100, ge=1, le=1000, description="WB page size"),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Manual ingestion entrypoint:
    pull WB reviews and upsert into unified `interactions`.
    """
    try:
        result = await ingest_wb_reviews_to_interactions(
            db=db,
            seller_id=current_seller.id,
            marketplace=current_seller.marketplace or "wildberries",
            only_unanswered=only_unanswered,
            nm_id=nm_id,
            max_items=max_items,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync WB reviews: {exc}",
        ) from exc

    return InteractionSyncResponse(
        seller_id=current_seller.id,
        channel="review",
        source="wb_api",
        **result.as_dict(),
    )


@router.post("/sync/questions", response_model=InteractionSyncResponse)
async def sync_questions(
    nm_id: Optional[int] = Query(None, ge=1, description="Filter sync by WB nmId"),
    only_unanswered: bool = Query(False, description="Sync only unanswered questions"),
    max_items: int = Query(300, ge=1, le=5000, description="Max questions to ingest"),
    page_size: int = Query(100, ge=1, le=1000, description="WB page size"),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Manual ingestion entrypoint:
    pull WB questions and upsert into unified `interactions`.
    """
    try:
        result = await ingest_wb_questions_to_interactions(
            db=db,
            seller_id=current_seller.id,
            marketplace=current_seller.marketplace or "wildberries",
            only_unanswered=only_unanswered,
            nm_id=nm_id,
            max_items=max_items,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync WB questions: {exc}",
        ) from exc

    return InteractionSyncResponse(
        seller_id=current_seller.id,
        channel="question",
        source="wb_api",
        **result.as_dict(),
    )


@router.post("/sync/chats", response_model=InteractionSyncResponse)
async def sync_chats(
    max_items: int = Query(500, ge=1, le=5000, description="Max chats to ingest"),
    direct_wb_fetch: bool = Query(
        False,
        description="If true and local chats table is empty, pull chats directly from WB events API",
    ),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Build channel=chat interactions from already-synced WB chats.
    """
    try:
        stats = await ingest_chat_interactions(
            db=db,
            seller_id=current_seller.id,
            max_items=max_items,
            direct_wb_fetch=direct_wb_fetch,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync chat interactions: {exc}",
        ) from exc

    return InteractionSyncResponse(
        seller_id=current_seller.id,
        channel="chat",
        source="wb_api",
        **stats,
    )


@router.get("/metrics/quality", response_model=InteractionQualityMetricsResponse)
async def quality_metrics(
    days: int = Query(30, ge=1, le=365, description="Rolling window in days"),
    channel: Optional[str] = Query(None, description="Optional channel filter: review/question/chat"),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get quality + pipeline metrics for unified interactions."""
    metrics = await get_quality_metrics(
        db=db,
        seller_id=current_seller.id,
        days=days,
        channel=channel,
    )

    return InteractionQualityMetricsResponse(
        period_days=metrics["period_days"],
        generated_from=metrics["generated_from"],
        generated_to=metrics["generated_to"],
        totals=InteractionQualityTotals(**metrics["totals"]),
        by_channel=[InteractionChannelQuality(**item) for item in metrics["by_channel"]],
        pipeline=InteractionPipelineMetrics(
            interactions_total=metrics["pipeline"]["interactions_total"],
            needs_response_total=metrics["pipeline"]["needs_response_total"],
            responded_total=metrics["pipeline"]["responded_total"],
            by_channel=[InteractionChannelPipeline(**item) for item in metrics["pipeline"]["by_channel"]],
        ),
    )


@router.get("/metrics/quality-history", response_model=InteractionQualityHistoryResponse)
async def quality_history(
    days: int = Query(30, ge=1, le=365, description="Rolling window in days"),
    channel: Optional[str] = Query(None, description="Optional channel filter: review/question/chat"),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get day-level quality history for charts."""
    history = await get_quality_history(
        db=db,
        seller_id=current_seller.id,
        days=days,
        channel=channel,
    )
    return InteractionQualityHistoryResponse(
        period_days=history["period_days"],
        generated_from=history["generated_from"],
        generated_to=history["generated_to"],
        series=[InteractionQualityHistoryPoint(**item) for item in history["series"]],
    )


@router.get("/metrics/ops-alerts", response_model=InteractionOpsAlertsResponse)
async def ops_alerts(
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get operational alerts for pilot reliability and SLA monitoring."""
    payload = await get_ops_alerts(
        db=db,
        seller_id=current_seller.id,
    )
    return InteractionOpsAlertsResponse(
        generated_at=payload["generated_at"],
        question_sla=payload["question_sla"],
        quality_regression=payload["quality_regression"],
        sync_health=payload.get("sync_health"),
        alerts=[InteractionOpsAlert(**item) for item in payload["alerts"]],
    )


@router.get("/metrics/pilot-readiness", response_model=InteractionPilotReadinessResponse)
async def pilot_readiness(
    max_sync_age_minutes: int = Query(30, ge=5, le=1440, description="Max allowed age of last sync"),
    max_overdue_questions: int = Query(0, ge=0, le=10000, description="Max allowed overdue questions"),
    max_manual_rate: float = Query(0.6, ge=0, le=1, description="Target upper bound for manual reply rate"),
    max_open_backlog: int = Query(250, ge=0, le=100000, description="Target upper bound for open backlog"),
    min_reply_activity: int = Query(1, ge=0, le=10000, description="Min reply activity baseline to pass check"),
    reply_activity_window_days: int = Query(
        30,
        ge=1,
        le=365,
        description="Rolling window (days) for reply activity baseline",
    ),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Pilot go/no-go readiness matrix for current seller."""
    payload = await get_pilot_readiness(
        db=db,
        seller_id=current_seller.id,
        sync_status=current_seller.sync_status,
        last_sync_at=current_seller.last_sync_at,
        sync_error=current_seller.sync_error,
        max_sync_age_minutes=max_sync_age_minutes,
        max_overdue_questions=max_overdue_questions,
        max_manual_rate=max_manual_rate,
        max_open_backlog=max_open_backlog,
        min_reply_activity=min_reply_activity,
        reply_activity_window_days=reply_activity_window_days,
    )
    return InteractionPilotReadinessResponse(
        generated_at=payload["generated_at"],
        go_no_go=payload["go_no_go"],
        decision=payload["decision"],
        summary=InteractionPilotReadinessSummary(**payload["summary"]),
        thresholds=payload["thresholds"],
        checks=[InteractionPilotReadinessCheck(**item) for item in payload["checks"]],
    )


@router.get("/metrics/revenue", response_model=RevenueImpactResponse)
async def revenue_impact(
    period_days: int = Query(30, ge=1, le=365, description="Rolling window in days"),
    avg_order_value: Optional[float] = Query(
        None, ge=0, description="Average order value in roubles (default 2000)",
    ),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue impact analytics for current seller.

    Calculates monetary impact of communication quality:
    - Revenue at risk from unresolved negative reviews
    - Revenue saved by responding to negatives within SLA
    - Potential additional savings with full coverage
    - Response time ROI from fast question responses
    """
    payload = await get_revenue_impact(
        db=db,
        seller_id=current_seller.id,
        period_days=period_days,
        avg_order_value=avg_order_value,
    )
    return RevenueImpactResponse(**payload)


@router.get("/health/celery")
async def celery_health():
    """
    Get Celery worker and scheduler health status.

    Returns:
        dict with:
        - worker_alive: bool
        - active_tasks: int (currently executing)
        - scheduled_tasks: int (from beat)
        - last_heartbeat: datetime | None
        - queue_length: int (reserved tasks)
        - status: "healthy" | "degraded" | "down"

    Status logic:
    - "healthy": worker alive + queue_length < 100
    - "degraded": worker alive but queue_length >= 100
    - "down": worker not responding

    Note: This endpoint is not seller-scoped (no auth required) for ops monitoring.
    """
    health = get_celery_health(timeout=1)
    return health


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: int,
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get interaction by ID."""
    result = await db.execute(select(Interaction).where(Interaction.id == interaction_id))
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found",
        )

    require_seller_ownership(interaction.seller_id, current_seller)

    return InteractionResponse.model_validate(interaction)


@router.get("/{interaction_id}/timeline", response_model=InteractionTimelineResponse)
async def get_interaction_timeline(
    interaction_id: int,
    max_items: int = Query(100, ge=1, le=300, description="Max timeline steps"),
    product_window_days: int = Query(
        45,
        ge=1,
        le=180,
        description="Time window for deterministic product-level timeline",
    ),
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get deterministic cross-channel thread timeline for one interaction."""
    result = await db.execute(select(Interaction).where(Interaction.id == interaction_id))
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found",
        )

    require_seller_ownership(interaction.seller_id, current_seller)

    timeline = await get_deterministic_thread_timeline(
        db=db,
        interaction=interaction,
        max_items=max_items,
        product_window_days=product_window_days,
    )

    return InteractionTimelineResponse(
        interaction_id=timeline["interaction_id"],
        thread_scope=timeline["thread_scope"],
        thread_key=timeline["thread_key"],
        channels_present=timeline["channels_present"],
        steps=[InteractionTimelineStep(**item) for item in timeline["steps"]],
    )


@router.post("/{interaction_id}/ai-draft", response_model=InteractionDraftResponse)
async def generate_ai_draft(
    interaction_id: int,
    payload: InteractionDraftRequest,
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate AI draft for interaction (review/question/chat).
    """
    result = await db.execute(select(Interaction).where(Interaction.id == interaction_id))
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found",
        )

    require_seller_ownership(interaction.seller_id, current_seller)

    cached = None
    if isinstance(interaction.extra_data, dict):
        cached = interaction.extra_data.get("last_ai_draft")

    if cached and not payload.force_regenerate:
        record_draft_event(
            db=db,
            interaction=interaction,
            source=str(cached.get("source", "cached")),
            force_regenerate=False,
            cached=True,
        )
        await db.commit()
        return InteractionDraftResponse(
            interaction=InteractionResponse.model_validate(interaction),
            draft_text=cached.get("text", ""),
            intent=cached.get("intent"),
            sentiment=cached.get("sentiment"),
            sla_priority=cached.get("sla_priority"),
            recommendation_reason=cached.get("recommendation_reason"),
            source="cached",
            guardrail_warnings=cached.get("guardrail_warnings", []),
        )

    try:
        draft = await generate_interaction_draft(db=db, interaction=interaction)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate draft: {exc}",
        ) from exc

    base_meta = interaction.extra_data if isinstance(interaction.extra_data, dict) else {}
    interaction.extra_data = {
        **base_meta,
        "last_ai_draft": draft.as_dict(),
    }
    record_draft_event(
        db=db,
        interaction=interaction,
        source=draft.source,
        force_regenerate=payload.force_regenerate,
        cached=False,
    )
    await db.commit()
    await db.refresh(interaction)

    return InteractionDraftResponse(
        interaction=InteractionResponse.model_validate(interaction),
        draft_text=draft.text,
        intent=draft.intent,
        sentiment=draft.sentiment,
        sla_priority=draft.sla_priority,
        recommendation_reason=draft.recommendation_reason,
        source=draft.source,
        guardrail_warnings=draft.guardrail_warnings or [],
    )


@router.post("/{interaction_id}/reply", response_model=InteractionReplyResponse)
async def reply_to_interaction(
    interaction_id: int,
    payload: InteractionReplyRequest,
    current_seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Send reply from unified interaction card.

    Implemented channels:
    - review -> WB feedbacks answer endpoint
    - question -> WB questions patch endpoint
    - chat -> create outgoing message and dispatch marketplace send task
    """
    result = await db.execute(select(Interaction).where(Interaction.id == interaction_id))
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction {interaction_id} not found",
        )

    require_seller_ownership(interaction.seller_id, current_seller)

    reply_text = payload.text.strip()
    if not reply_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reply text is required",
        )

    # --- Pre-send guardrail validation (blocking) ---
    customer_text = interaction.text or ""
    validation = validate_reply_text(reply_text, interaction.channel or "review", customer_text)
    if not validation["valid"]:
        violation_msgs = [v.get("message", str(v)) for v in validation["violations"]]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Reply blocked by guardrails",
                "violations": validation["violations"],
                "warnings": validation["warnings"],
                "summary": "; ".join(violation_msgs),
            },
        )

    try:
        if interaction.channel == "review":
            connector = await get_wb_feedbacks_connector_for_seller(current_seller.id, db)
            await connector.answer_feedback(
                feedback_id=interaction.external_id,
                text=reply_text,
            )
        elif interaction.channel == "question":
            connector = await get_wb_questions_connector_for_seller(current_seller.id, db)
            state = "wbRu"
            if isinstance(interaction.extra_data, dict):
                raw_state = interaction.extra_data.get("state")
                if raw_state in {"wbRu", "none"}:
                    state = raw_state
            await connector.patch_question(
                question_id=interaction.external_id,
                state=state,
                answer_text=reply_text,
            )
        elif interaction.channel == "chat":
            chat = None
            if isinstance(interaction.extra_data, dict):
                raw_chat_id = interaction.extra_data.get("chat_id")
                if isinstance(raw_chat_id, int):
                    chat_result = await db.execute(
                        select(Chat).where(
                            and_(Chat.id == raw_chat_id, Chat.seller_id == current_seller.id)
                        )
                    )
                    chat = chat_result.scalar_one_or_none()
                elif isinstance(raw_chat_id, str) and raw_chat_id.isdigit():
                    chat_result = await db.execute(
                        select(Chat).where(
                            and_(Chat.id == int(raw_chat_id), Chat.seller_id == current_seller.id)
                        )
                    )
                    chat = chat_result.scalar_one_or_none()

            if not chat:
                chat_result = await db.execute(
                    select(Chat).where(
                        and_(
                            Chat.seller_id == current_seller.id,
                            Chat.marketplace_chat_id == interaction.external_id,
                        )
                    )
                )
                chat = chat_result.scalar_one_or_none()

            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Linked chat not found for this interaction",
                )

            has_credentials = bool(current_seller.api_key_encrypted)
            message = Message(
                chat_id=chat.id,
                external_message_id=f"pending_{uuid.uuid4().hex[:12]}",
                direction="outgoing",
                text=reply_text,
                author_type="seller",
                status="pending" if has_credentials else "sent",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(message)
            await db.flush()

            chat.last_message_at = message.sent_at
            chat.last_message_preview = reply_text[:500]
            if has_credentials:
                try:
                    from app.tasks.sync import send_message_to_marketplace

                    send_message_to_marketplace.delay(message.id)
                except Exception:
                    # Keep message pending; periodic worker can retry later.
                    pass
            else:
                chat.chat_status = "responded"
                chat.unread_count = 0
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported interaction channel: {interaction.channel}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send reply: {exc}",
        ) from exc

    outcome = record_reply_events(
        db=db,
        interaction=interaction,
        reply_text=reply_text,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    interaction.status = "responded"
    interaction.needs_response = False
    interaction.priority = "low"
    if isinstance(interaction.extra_data, dict):
        interaction.extra_data = {
            **interaction.extra_data,
            "last_reply_text": reply_text[:500],
            "last_reply_outcome": outcome,
            # If WB doesn't reflect the answer immediately (moderation / propagation),
            # ingestion can keep the item in responded state for a short window.
            "last_reply_source": "agentiq",
            "last_reply_at": now_iso,
            "wb_sync_state": "pending",
        }
    await db.commit()
    await db.refresh(interaction)

    return InteractionReplyResponse(
        interaction=InteractionResponse.model_validate(interaction),
        result="sent",
    )
