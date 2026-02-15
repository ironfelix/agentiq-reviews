"""Quality metrics and event tracking for unified interactions."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent
from app.services.sync_metrics import sync_health_monitor

EVENT_DRAFT_GENERATED = "draft_generated"
EVENT_DRAFT_CACHE_HIT = "draft_cache_hit"
EVENT_REPLY_SENT = "reply_sent"
EVENT_DRAFT_ACCEPTED = "draft_accepted"
EVENT_DRAFT_EDITED = "draft_edited"
EVENT_REPLY_MANUAL = "reply_manual"


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def classify_reply_quality(interaction: Interaction, reply_text: str) -> tuple[str, Optional[str]]:
    """
    Classify reply quality outcome:
    - draft_accepted: reply equals generated draft
    - draft_edited: draft exists but reply differs
    - reply_manual: no draft existed
    """
    draft_source: Optional[str] = None
    if not isinstance(interaction.extra_data, dict):
        return EVENT_REPLY_MANUAL, draft_source

    draft_meta = interaction.extra_data.get("last_ai_draft")
    if not isinstance(draft_meta, dict):
        return EVENT_REPLY_MANUAL, draft_source

    draft_text = draft_meta.get("text")
    if not isinstance(draft_text, str) or not draft_text.strip():
        return EVENT_REPLY_MANUAL, draft_source

    raw_source = draft_meta.get("source")
    if isinstance(raw_source, str):
        draft_source = raw_source

    if _normalize_text(draft_text) == _normalize_text(reply_text):
        return EVENT_DRAFT_ACCEPTED, draft_source

    return EVENT_DRAFT_EDITED, draft_source


def record_interaction_event(
    db: AsyncSession,
    interaction: Interaction,
    event_type: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Append event to interaction event stream."""
    event = InteractionEvent(
        interaction_id=interaction.id,
        seller_id=interaction.seller_id,
        channel=interaction.channel,
        event_type=event_type,
        details=details or {},
    )
    db.add(event)


def record_draft_event(
    db: AsyncSession,
    interaction: Interaction,
    *,
    source: str,
    force_regenerate: bool,
    cached: bool,
) -> None:
    """Record draft generation/cache usage event."""
    event_type = EVENT_DRAFT_CACHE_HIT if cached else EVENT_DRAFT_GENERATED
    record_interaction_event(
        db=db,
        interaction=interaction,
        event_type=event_type,
        details={
            "source": source,
            "force_regenerate": force_regenerate,
        },
    )


def record_reply_events(
    db: AsyncSession,
    interaction: Interaction,
    reply_text: str,
) -> str:
    """Record reply event and return quality outcome."""
    outcome, draft_source = classify_reply_quality(interaction, reply_text)
    record_interaction_event(
        db=db,
        interaction=interaction,
        event_type=EVENT_REPLY_SENT,
        details={"text_len": len(reply_text)},
    )
    record_interaction_event(
        db=db,
        interaction=interaction,
        event_type=outcome,
        details={
            "text_len": len(reply_text),
            "draft_source": draft_source,
        },
    )
    return outcome


def _safe_rate(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 4)


def _iter_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _quality_window_rates(
    db: AsyncSession,
    *,
    seller_id: int,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, float]:
    stmt = (
        select(
            func.sum(case((InteractionEvent.event_type == EVENT_REPLY_SENT, 1), else_=0)).label("replies_total"),
            func.sum(case((InteractionEvent.event_type == EVENT_REPLY_MANUAL, 1), else_=0)).label("reply_manual"),
            func.sum(case((InteractionEvent.event_type == EVENT_DRAFT_ACCEPTED, 1), else_=0)).label("draft_accepted"),
        )
        .where(
            and_(
                InteractionEvent.seller_id == seller_id,
                InteractionEvent.created_at >= start_at,
                InteractionEvent.created_at < end_at,
            )
        )
    )
    result = await db.execute(stmt)
    row = result.one()
    replies_total = int(row.replies_total or 0)
    manual = int(row.reply_manual or 0)
    accepted = int(row.draft_accepted or 0)
    return {
        "replies_total": float(replies_total),
        "manual_rate": _safe_rate(manual, replies_total),
        "accept_rate": _safe_rate(accepted, replies_total),
    }


async def _observed_replied_interactions_count(
    db: AsyncSession,
    *,
    seller_id: int,
    start_at: datetime,
    end_at: datetime,
    channels: Sequence[str],
) -> int:
    """
    Count interactions that are already marked as answered in source data
    (even if reply was not sent via our /reply endpoint).

    This is used as a readiness baseline fallback for early pilot stages,
    where historical replies existed before unified dispatcher rollout.
    """
    if not channels:
        return 0

    stmt = (
        select(func.count(Interaction.id))
        .where(
            and_(
                Interaction.seller_id == seller_id,
                Interaction.channel.in_(list(channels)),
                Interaction.needs_response.is_(False),
                func.coalesce(Interaction.occurred_at, Interaction.updated_at) >= start_at,
                func.coalesce(Interaction.occurred_at, Interaction.updated_at) <= end_at,
            )
        )
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_quality_metrics(
    db: AsyncSession,
    *,
    seller_id: int,
    days: int = 30,
    channel: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregate quality metrics for dashboard/API."""
    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=max(1, days))

    conditions = [
        InteractionEvent.seller_id == seller_id,
        InteractionEvent.created_at >= start_at,
        InteractionEvent.created_at <= now,
    ]
    if channel:
        conditions.append(InteractionEvent.channel == channel)

    events_stmt = (
        select(
            InteractionEvent.channel,
            InteractionEvent.event_type,
            func.count().label("count"),
        )
        .where(and_(*conditions))
        .group_by(InteractionEvent.channel, InteractionEvent.event_type)
    )
    events_result = await db.execute(events_stmt)
    rows = events_result.all()

    by_channel_counts: dict[str, dict[str, int]] = {}
    totals_by_type: dict[str, int] = {}
    for row in rows:
        channel_name = row.channel
        event_type = row.event_type
        count = int(row.count or 0)
        by_channel_counts.setdefault(channel_name, {})
        by_channel_counts[channel_name][event_type] = count
        totals_by_type[event_type] = totals_by_type.get(event_type, 0) + count

    channels_payload = []
    for channel_name, counts in sorted(by_channel_counts.items()):
        replies_total = counts.get(EVENT_REPLY_SENT, 0)
        accepted = counts.get(EVENT_DRAFT_ACCEPTED, 0)
        edited = counts.get(EVENT_DRAFT_EDITED, 0)
        manual = counts.get(EVENT_REPLY_MANUAL, 0)
        channels_payload.append(
            {
                "channel": channel_name,
                "replies_total": replies_total,
                "draft_generated": counts.get(EVENT_DRAFT_GENERATED, 0),
                "draft_cache_hits": counts.get(EVENT_DRAFT_CACHE_HIT, 0),
                "draft_accepted": accepted,
                "draft_edited": edited,
                "reply_manual": manual,
                "accept_rate": _safe_rate(accepted, replies_total),
                "edit_rate": _safe_rate(edited, replies_total),
                "manual_rate": _safe_rate(manual, replies_total),
            }
        )

    replies_total = totals_by_type.get(EVENT_REPLY_SENT, 0)
    totals = {
        "replies_total": replies_total,
        "draft_generated": totals_by_type.get(EVENT_DRAFT_GENERATED, 0),
        "draft_cache_hits": totals_by_type.get(EVENT_DRAFT_CACHE_HIT, 0),
        "draft_accepted": totals_by_type.get(EVENT_DRAFT_ACCEPTED, 0),
        "draft_edited": totals_by_type.get(EVENT_DRAFT_EDITED, 0),
        "reply_manual": totals_by_type.get(EVENT_REPLY_MANUAL, 0),
        "accept_rate": _safe_rate(totals_by_type.get(EVENT_DRAFT_ACCEPTED, 0), replies_total),
        "edit_rate": _safe_rate(totals_by_type.get(EVENT_DRAFT_EDITED, 0), replies_total),
        "manual_rate": _safe_rate(totals_by_type.get(EVENT_REPLY_MANUAL, 0), replies_total),
    }

    interaction_conditions = [Interaction.seller_id == seller_id]
    if channel:
        interaction_conditions.append(Interaction.channel == channel)

    pipeline_stmt = (
        select(
            Interaction.channel,
            func.count().label("total"),
            func.sum(case((Interaction.needs_response.is_(True), 1), else_=0)).label("needs_response"),
            func.sum(case((Interaction.status == "responded", 1), else_=0)).label("responded"),
        )
        .where(and_(*interaction_conditions))
        .group_by(Interaction.channel)
    )
    pipeline_result = await db.execute(pipeline_stmt)

    by_channel_pipeline = []
    interactions_total = 0
    needs_response_total = 0
    responded_total = 0
    for row in pipeline_result.all():
        total = int(row.total or 0)
        needs = int(row.needs_response or 0)
        responded = int(row.responded or 0)
        interactions_total += total
        needs_response_total += needs
        responded_total += responded
        by_channel_pipeline.append(
            {
                "channel": row.channel,
                "interactions_total": total,
                "needs_response_total": needs,
                "responded_total": responded,
            }
        )

    return {
        "period_days": max(1, days),
        "generated_from": start_at,
        "generated_to": now,
        "totals": totals,
        "by_channel": channels_payload,
        "pipeline": {
            "interactions_total": interactions_total,
            "needs_response_total": needs_response_total,
            "responded_total": responded_total,
            "by_channel": by_channel_pipeline,
        },
    }


async def get_quality_history(
    db: AsyncSession,
    *,
    seller_id: int,
    days: int = 30,
    channel: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregate day-level quality history for trend charts."""
    now = datetime.now(timezone.utc)
    days = max(1, days)
    start_day = (now - timedelta(days=days - 1)).date()
    end_day = now.date()
    start_at = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)

    conditions = [
        InteractionEvent.seller_id == seller_id,
        InteractionEvent.created_at >= start_at,
        InteractionEvent.created_at <= now,
    ]
    if channel:
        conditions.append(InteractionEvent.channel == channel)

    day_expr = func.date(InteractionEvent.created_at)
    stmt = (
        select(
            day_expr.label("day"),
            func.sum(case((InteractionEvent.event_type == EVENT_REPLY_SENT, 1), else_=0)).label("replies_total"),
            func.sum(case((InteractionEvent.event_type == EVENT_DRAFT_ACCEPTED, 1), else_=0)).label("draft_accepted"),
            func.sum(case((InteractionEvent.event_type == EVENT_DRAFT_EDITED, 1), else_=0)).label("draft_edited"),
            func.sum(case((InteractionEvent.event_type == EVENT_REPLY_MANUAL, 1), else_=0)).label("reply_manual"),
        )
        .where(and_(*conditions))
        .group_by(day_expr)
        .order_by(day_expr.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day_raw = row.day
        if isinstance(day_raw, str):
            day_key = day_raw
        else:
            day_key = str(day_raw)
        by_day[day_key] = {
            "replies_total": int(row.replies_total or 0),
            "draft_accepted": int(row.draft_accepted or 0),
            "draft_edited": int(row.draft_edited or 0),
            "reply_manual": int(row.reply_manual or 0),
        }

    series: list[dict[str, Any]] = []
    for day in _iter_days(start_day, end_day):
        day_key = day.isoformat()
        counters = by_day.get(
            day_key,
            {
                "replies_total": 0,
                "draft_accepted": 0,
                "draft_edited": 0,
                "reply_manual": 0,
            },
        )
        replies_total = counters["replies_total"]
        accepted = counters["draft_accepted"]
        edited = counters["draft_edited"]
        manual = counters["reply_manual"]
        series.append(
            {
                "date": day_key,
                "replies_total": replies_total,
                "draft_accepted": accepted,
                "draft_edited": edited,
                "reply_manual": manual,
                "accept_rate": _safe_rate(accepted, replies_total),
                "edit_rate": _safe_rate(edited, replies_total),
                "manual_rate": _safe_rate(manual, replies_total),
            }
        )

    return {
        "period_days": days,
        "generated_from": start_at,
        "generated_to": now,
        "series": series,
    }


async def get_ops_alerts(
    db: AsyncSession,
    *,
    seller_id: int,
    sla_warning_minutes: int = 60,
    manual_rate_regression_threshold: float = 0.15,
) -> dict[str, Any]:
    """
    Operational alerts for pilot:
    - questions SLA overdue / near due
    - quality regression in manual-rate compared to previous week
    """
    now = datetime.now(timezone.utc)

    questions_stmt = (
        select(
            Interaction.id,
            Interaction.extra_data,
        )
        .where(
            and_(
                Interaction.seller_id == seller_id,
                Interaction.channel == "question",
                Interaction.needs_response.is_(True),
            )
        )
    )
    questions_result = await db.execute(questions_stmt)
    open_questions = questions_result.all()

    overdue_total = 0
    due_soon_total = 0
    with_sla_total = 0
    oldest_overdue_minutes: Optional[int] = None
    for row in open_questions:
        meta = row.extra_data if isinstance(row.extra_data, dict) else {}
        due_at = _parse_iso_datetime(meta.get("sla_due_at"))
        if not due_at:
            continue
        with_sla_total += 1
        delta_minutes = int((due_at - now).total_seconds() / 60)
        if delta_minutes < 0:
            overdue_total += 1
            overdue_age = abs(delta_minutes)
            if oldest_overdue_minutes is None or overdue_age > oldest_overdue_minutes:
                oldest_overdue_minutes = overdue_age
        elif delta_minutes <= sla_warning_minutes:
            due_soon_total += 1

    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    previous_end = current_start

    current_rates = await _quality_window_rates(
        db=db,
        seller_id=seller_id,
        start_at=current_start,
        end_at=now,
    )
    previous_rates = await _quality_window_rates(
        db=db,
        seller_id=seller_id,
        start_at=previous_start,
        end_at=previous_end,
    )

    manual_delta = round(current_rates["manual_rate"] - previous_rates["manual_rate"], 4)
    quality_regression = manual_delta >= manual_rate_regression_threshold

    alerts: list[dict[str, Any]] = []
    if overdue_total > 0:
        alerts.append(
            {
                "code": "sla_overdue_questions",
                "severity": "high",
                "title": "Есть просроченные вопросы",
                "message": f"Просрочено {overdue_total} вопросов",
            }
        )
    if due_soon_total > 0:
        alerts.append(
            {
                "code": "sla_due_soon_questions",
                "severity": "medium",
                "title": "Вопросы скоро выйдут из SLA",
                "message": f"{due_soon_total} вопросов с дедлайном <= {sla_warning_minutes} мин",
            }
        )
    if quality_regression:
        alerts.append(
            {
                "code": "quality_manual_rate_regression",
                "severity": "high",
                "title": "Просадка качества ответов",
                "message": f"Manual-rate вырос на {round(manual_delta * 100, 1)} п.п. за 7 дней",
            }
        )

    # --- Sync health alerts (from in-memory ring buffer) ---
    sync_health = sync_health_monitor.check_sync_health(seller_id)
    sync_alerts = sync_health_monitor.get_active_alerts(seller_id)
    alerts.extend(sync_alerts)

    # --- Celery health alerts ---
    from app.services.celery_health import get_celery_health
    celery_health = get_celery_health(timeout=5)
    if celery_health["status"] == "down":
        alerts.append(
            {
                "code": "celery_worker_down",
                "severity": "critical",
                "title": "Celery worker не отвечает",
                "message": "Фоновые задачи не выполняются (sync, AI analysis, SLA escalation)",
            }
        )
    elif celery_health["status"] == "degraded":
        alerts.append(
            {
                "code": "celery_queue_high",
                "severity": "medium",
                "title": "Большая очередь задач в Celery",
                "message": f"В очереди {celery_health['queue_length']} задач (порог: 100)",
            }
        )

    return {
        "generated_at": now,
        "question_sla": {
            "open_questions_total": len(open_questions),
            "with_sla_total": with_sla_total,
            "overdue_total": overdue_total,
            "due_soon_total": due_soon_total,
            "oldest_overdue_minutes": oldest_overdue_minutes,
        },
        "quality_regression": {
            "current_window_days": 7,
            "previous_window_days": 7,
            "current_manual_rate": current_rates["manual_rate"],
            "previous_manual_rate": previous_rates["manual_rate"],
            "manual_rate_delta": manual_delta,
            "regression_detected": quality_regression,
            "manual_rate_regression_threshold": manual_rate_regression_threshold,
        },
        "sync_health": sync_health,
        "celery_health": celery_health,
        "alerts": alerts,
    }


async def get_pilot_readiness(
    db: AsyncSession,
    *,
    seller_id: int,
    sync_status: Optional[str],
    last_sync_at: Optional[datetime],
    sync_error: Optional[str],
    required_channels: Sequence[str] = ("review", "question"),
    recommended_channels: Sequence[str] = ("chat",),
    max_sync_age_minutes: int = 30,
    max_overdue_questions: int = 0,
    max_manual_rate: float = 0.6,
    max_open_backlog: int = 250,
    min_reply_activity: int = 1,
    reply_activity_window_days: int = 30,
) -> dict[str, Any]:
    """
    Compute pilot go/no-go readiness from operational and quality signals.

    Go/No-Go is blocked only by checks explicitly marked as blocker.
    """
    now = datetime.now(timezone.utc)
    checks: list[dict[str, Any]] = []

    def add_check(
        *,
        code: str,
        title: str,
        status: str,
        blocker: bool,
        details: str,
    ) -> None:
        checks.append(
            {
                "code": code,
                "title": title,
                "status": status,
                "blocker": blocker,
                "details": details,
            }
        )

    normalized_last_sync_at = _normalize_datetime(last_sync_at)
    sync_age_minutes: Optional[int] = None
    if normalized_last_sync_at is not None:
        sync_age_minutes = int((now - normalized_last_sync_at).total_seconds() / 60)

    latest_interaction_stmt = select(func.max(Interaction.updated_at)).where(Interaction.seller_id == seller_id)
    latest_interaction_result = await db.execute(latest_interaction_stmt)
    latest_interaction_at = _normalize_datetime(latest_interaction_result.scalar_one_or_none())
    latest_interaction_age_minutes: Optional[int] = None
    if latest_interaction_at is not None:
        latest_interaction_age_minutes = int((now - latest_interaction_at).total_seconds() / 60)

    if sync_status == "error":
        add_check(
            code="sync_status",
            title="Sync статус",
            status="fail",
            blocker=True,
            details=f"Последняя sync завершилась ошибкой: {sync_error or 'unknown error'}",
        )
    elif normalized_last_sync_at is None:
        if latest_interaction_age_minutes is not None and latest_interaction_age_minutes <= max_sync_age_minutes:
            add_check(
                code="sync_freshness",
                title="Свежесть данных",
                status="pass",
                blocker=False,
                details=(
                    "Нет last_sync_at, но данные interactions обновлены "
                    f"{latest_interaction_age_minutes} мин назад."
                ),
            )
        else:
            add_check(
                code="sync_freshness",
                title="Свежесть данных",
                status="fail",
                blocker=True,
                details="Нет last_sync_at: сначала нужен успешный sync перед пилотом.",
            )
    elif sync_age_minutes is not None and sync_age_minutes > max_sync_age_minutes:
        add_check(
            code="sync_freshness",
            title="Свежесть данных",
            status="fail",
            blocker=True,
            details=f"Последний sync {sync_age_minutes} мин назад (лимит {max_sync_age_minutes} мин).",
        )
    elif sync_status == "syncing":
        add_check(
            code="sync_status",
            title="Sync статус",
            status="warn",
            blocker=False,
            details="Sync в процессе: дождитесь завершения перед пилотным прогоном.",
        )
    else:
        add_check(
            code="sync_freshness",
            title="Свежесть данных",
            status="pass",
            blocker=False,
            details=f"Последний sync {sync_age_minutes or 0} мин назад.",
        )

    quality = await get_quality_metrics(
        db=db,
        seller_id=seller_id,
        days=30,
    )
    ops_alerts = await get_ops_alerts(
        db=db,
        seller_id=seller_id,
    )

    pipeline_counts = {
        item["channel"]: int(item.get("interactions_total") or 0)
        for item in quality["pipeline"]["by_channel"]
    }
    missing_required_channels = [channel for channel in required_channels if pipeline_counts.get(channel, 0) <= 0]
    if missing_required_channels:
        add_check(
            code="channel_coverage",
            title="Покрытие каналов",
            status="fail",
            blocker=True,
            details=f"Нет данных по обязательным каналам: {', '.join(missing_required_channels)}",
        )
    else:
        add_check(
            code="channel_coverage",
            title="Покрытие каналов",
            status="pass",
            blocker=False,
            details=f"Есть данные по обязательным каналам: {', '.join(required_channels)}.",
        )

    missing_recommended_channels = [channel for channel in recommended_channels if pipeline_counts.get(channel, 0) <= 0]
    if missing_recommended_channels:
        add_check(
            code="channel_coverage_recommended",
            title="Покрытие рекомендованных каналов",
            status="warn",
            blocker=False,
            details=f"Нет данных по рекомендованным каналам: {', '.join(missing_recommended_channels)}",
        )
    else:
        add_check(
            code="channel_coverage_recommended",
            title="Покрытие рекомендованных каналов",
            status="pass",
            blocker=False,
            details=f"Есть данные по рекомендованным каналам: {', '.join(recommended_channels)}",
        )

    overdue_total = int(ops_alerts["question_sla"].get("overdue_total") or 0)
    if overdue_total > max_overdue_questions:
        add_check(
            code="question_sla_overdue",
            title="SLA вопросов",
            status="fail",
            blocker=True,
            details=f"Просрочено {overdue_total} вопросов (лимит {max_overdue_questions}).",
        )
    else:
        add_check(
            code="question_sla_overdue",
            title="SLA вопросов",
            status="pass",
            blocker=False,
            details=f"Просроченных вопросов: {overdue_total}.",
        )

    manual_rate = float(quality["totals"].get("manual_rate") or 0.0)
    if manual_rate > max_manual_rate:
        add_check(
            code="quality_manual_rate",
            title="Manual rate",
            status="warn",
            blocker=False,
            details=(
                f"Manual rate {round(manual_rate * 100, 1)}% выше целевого "
                f"{round(max_manual_rate * 100, 1)}%."
            ),
        )
    else:
        add_check(
            code="quality_manual_rate",
            title="Manual rate",
            status="pass",
            blocker=False,
            details=f"Manual rate {round(manual_rate * 100, 1)}%.",
        )

    if bool(ops_alerts["quality_regression"].get("regression_detected")):
        delta = float(ops_alerts["quality_regression"].get("manual_rate_delta") or 0.0)
        add_check(
            code="quality_regression",
            title="Регрессия качества",
            status="warn",
            blocker=False,
            details=f"Manual-rate вырос на {round(delta * 100, 1)} п.п. week-over-week.",
        )
    else:
        add_check(
            code="quality_regression",
            title="Регрессия качества",
            status="pass",
            blocker=False,
            details="Регрессия quality не обнаружена.",
        )

    open_backlog = int(quality["pipeline"].get("needs_response_total") or 0)
    if open_backlog > max_open_backlog:
        add_check(
            code="open_backlog",
            title="Размер очереди",
            status="warn",
            blocker=False,
            details=f"Открытый backlog {open_backlog} (целевой <= {max_open_backlog}).",
        )
    else:
        add_check(
            code="open_backlog",
            title="Размер очереди",
            status="pass",
            blocker=False,
            details=f"Открытый backlog {open_backlog}.",
        )

    replies_total = int(quality["totals"].get("replies_total") or 0)
    if replies_total >= min_reply_activity:
        add_check(
            code="reply_activity",
            title="Активность ответов",
            status="pass",
            blocker=False,
            details=f"Ответов через dispatcher в окне: {replies_total}.",
        )
    else:
        reply_window_days = max(1, int(reply_activity_window_days))
        reply_window_start = now - timedelta(days=reply_window_days)
        observed_replied = await _observed_replied_interactions_count(
            db=db,
            seller_id=seller_id,
            start_at=reply_window_start,
            end_at=now,
            channels=required_channels,
        )
        if observed_replied >= min_reply_activity:
            add_check(
                code="reply_activity",
                title="Активность ответов",
                status="pass",
                blocker=False,
                details=(
                    "Нет reply_sent через dispatcher, но в source есть "
                    f"{observed_replied} отвеченных обращений за {reply_window_days} дн."
                ),
            )
        else:
            add_check(
                code="reply_activity",
                title="Активность ответов",
                status="warn",
                blocker=False,
                details=(
                    "За окно метрик нет reply_sent и не найден baseline answered "
                    f"по required каналам за {reply_window_days} дн."
                ),
            )

    failed = sum(1 for item in checks if item["status"] == "fail")
    warnings = sum(1 for item in checks if item["status"] == "warn")
    passed = sum(1 for item in checks if item["status"] == "pass")
    blockers = [item["code"] for item in checks if item["blocker"] and item["status"] == "fail"]
    go_no_go = len(blockers) == 0

    return {
        "generated_at": now,
        "go_no_go": go_no_go,
        "decision": "go" if go_no_go else "no-go",
        "summary": {
            "total_checks": len(checks),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "blockers": blockers,
        },
        "thresholds": {
            "required_channels": list(required_channels),
            "recommended_channels": list(recommended_channels),
            "max_sync_age_minutes": max_sync_age_minutes,
            "max_overdue_questions": max_overdue_questions,
            "max_manual_rate": max_manual_rate,
            "max_open_backlog": max_open_backlog,
            "min_reply_activity": min_reply_activity,
            "reply_activity_window_days": max(1, int(reply_activity_window_days)),
        },
        "checks": checks,
    }
