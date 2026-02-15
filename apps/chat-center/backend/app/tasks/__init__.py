"""Celery app configuration and task registry"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

# Celery app
celery_app = Celery(
    "agentiq_chat",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=["app.tasks.sync"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_soft_time_limit=120,  # 2 minutes soft limit
    task_time_limit=180,       # 3 minutes hard limit
    task_acks_late=True,       # Acknowledge after task completion
    worker_prefetch_multiplier=1,  # One task at a time per worker

    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,

    # Beat schedule (periodic tasks)
    beat_schedule={
        "sync-all-sellers-every-30s": {
            "task": "app.tasks.sync.sync_all_sellers",
            "schedule": 30.0,  # Every 30 seconds
        },
        "sync-all-seller-interactions-every-5min": {
            "task": "app.tasks.sync.sync_all_seller_interactions",
            "schedule": 300.0,  # Every 5 minutes
        },
        "check-sla-escalation-every-5min": {
            "task": "app.tasks.sync.check_sla_escalation",
            "schedule": 300.0,  # Every 5 minutes
        },
        "analyze-pending-chats-every-2min": {
            "task": "app.tasks.sync.analyze_pending_chats",
            "schedule": 120.0,  # Every 2 minutes
        },
        "process-auto-responses-every-3min": {
            "task": "app.tasks.sync.process_auto_responses",
            "schedule": 180.0,  # Every 3 minutes
        },
        "auto-close-inactive-chats-daily": {
            "task": "app.tasks.sync.auto_close_inactive_chats",
            "schedule": 86400.0,  # Every 24 hours
        },
    },
)
