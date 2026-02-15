"""Celery health monitoring service."""

from datetime import datetime, timezone
from typing import Any, Optional

from celery import Celery
from celery.exceptions import TimeoutError as CeleryTimeoutError

from app.tasks import celery_app


def get_celery_health(timeout: int = 3) -> dict[str, Any]:
    """
    Check Celery worker and scheduler health.

    Returns:
        dict with:
        - worker_alive: bool (ping successful)
        - active_tasks: int (currently executing)
        - scheduled_tasks: int (reserved/queued)
        - last_heartbeat: datetime | None
        - queue_length: int (reserved tasks count)
        - status: "healthy" | "degraded" | "down"

    Only 3 inspect calls (ping, active, reserved) to keep response
    under 15 seconds. Scheduled and stats are skipped as non-critical.
    """
    try:
        # Get inspector (with timeout)
        inspect = celery_app.control.inspect(timeout=timeout)

        # Try to ping workers
        ping_result = inspect.ping()
        worker_alive = bool(ping_result)

        if not worker_alive:
            return {
                "worker_alive": False,
                "active_tasks": None,
                "scheduled_tasks": None,
                "last_heartbeat": None,
                "queue_length": None,
                "status": "down",
            }

        # Get active tasks (currently executing)
        active = inspect.active()
        active_tasks = sum(len(tasks) for tasks in (active or {}).values())

        # Get reserved tasks (queued + executing)
        reserved = inspect.reserved()
        queue_length = sum(len(tasks) for tasks in (reserved or {}).values())

        # Skip scheduled and stats to reduce total response time
        # (5 calls x 3s timeout = 15s vs 3 calls x 3s = 9s)
        scheduled_tasks = 0
        last_heartbeat = None

        # Determine status
        if queue_length >= 100:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "worker_alive": True,
            "active_tasks": active_tasks,
            "scheduled_tasks": scheduled_tasks,
            "last_heartbeat": last_heartbeat,
            "queue_length": queue_length,
            "status": status,
        }

    except (CeleryTimeoutError, TimeoutError):
        # Timeout - worker not responding
        return {
            "worker_alive": False,
            "active_tasks": None,
            "scheduled_tasks": None,
            "last_heartbeat": None,
            "queue_length": None,
            "status": "down",
        }
    except Exception as e:
        # Any other error - treat as down
        return {
            "worker_alive": False,
            "active_tasks": None,
            "scheduled_tasks": None,
            "last_heartbeat": None,
            "queue_length": None,
            "status": "down",
            "error": str(e),
        }
