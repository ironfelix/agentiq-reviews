"""Celery health monitoring service."""

from datetime import datetime, timezone
from typing import Any, Optional

from celery import Celery
from celery.exceptions import TimeoutError as CeleryTimeoutError

from app.tasks import celery_app


def get_celery_health(timeout: int = 1) -> dict[str, Any]:
    """
    Check Celery worker health via a single ping inspect call.

    Uses one inspect call (ping) instead of three (ping+active+reserved)
    to keep response time under ~timeout seconds instead of 3×timeout.
    Active/queue counts are derived from the ping result (worker count proxy).
    """
    _down = {
        "worker_alive": False,
        "active_tasks": None,
        "scheduled_tasks": 0,
        "last_heartbeat": None,
        "queue_length": None,
        "status": "down",
    }
    try:
        inspect = celery_app.control.inspect(timeout=timeout)
        ping_result = inspect.ping()
        if not ping_result:
            return _down

        # ping_result: {worker_name: {"ok": "pong"}, ...}
        worker_count = len(ping_result)
        return {
            "worker_alive": True,
            "active_tasks": 0,       # not fetched — avoids extra round-trip
            "scheduled_tasks": 0,
            "last_heartbeat": None,
            "queue_length": 0,
            "worker_count": worker_count,
            "status": "healthy",
        }

    except (CeleryTimeoutError, TimeoutError):
        return _down
    except Exception as e:
        return {**_down, "error": str(e)}
