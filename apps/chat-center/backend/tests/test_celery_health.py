"""Tests for Celery health monitoring."""

import os

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.celery_health import get_celery_health


class TestCeleryHealthService:
    """Test suite for Celery health check service."""

    @patch('app.services.celery_health.celery_app')
    def test_healthy_state(self, mock_celery_app):
        """Test healthy Celery state with normal queue."""
        # Mock inspector responses
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {"worker1@hostname": {"ok": "pong"}}
        mock_inspect.active.return_value = {
            "worker1@hostname": [{"id": "task1", "name": "app.tasks.sync.sync_seller_chats"}]
        }
        mock_inspect.reserved.return_value = {
            "worker1@hostname": [
                {"id": "task1", "name": "app.tasks.sync.sync_seller_chats"},
                {"id": "task2", "name": "app.tasks.sync.analyze_chat_with_ai"}
            ]
        }
        mock_inspect.scheduled.return_value = {
            "worker1@hostname": []
        }
        mock_inspect.stats.return_value = {
            "worker1@hostname": {
                "clock": datetime.now(timezone.utc).timestamp()
            }
        }

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is True
        assert health["active_tasks"] == 1
        assert health["queue_length"] == 2
        assert health["scheduled_tasks"] == 0
        assert health["status"] == "healthy"
        # last_heartbeat is None since stats call was removed for performance
        assert health["last_heartbeat"] is None

    @patch('app.services.celery_health.celery_app')
    def test_degraded_state_high_queue(self, mock_celery_app):
        """Test degraded state when queue length >= 100."""
        # Mock inspector with high queue
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {"worker1@hostname": {"ok": "pong"}}
        mock_inspect.active.return_value = {"worker1@hostname": [{"id": f"task{i}"} for i in range(10)]}
        # 100+ reserved tasks
        mock_inspect.reserved.return_value = {"worker1@hostname": [{"id": f"task{i}"} for i in range(120)]}
        mock_inspect.scheduled.return_value = {"worker1@hostname": []}
        mock_inspect.stats.return_value = {
            "worker1@hostname": {"clock": datetime.now(timezone.utc).timestamp()}
        }

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is True
        assert health["active_tasks"] == 10
        assert health["queue_length"] == 120
        assert health["status"] == "degraded"

    @patch('app.services.celery_health.celery_app')
    def test_down_state_no_ping(self, mock_celery_app):
        """Test down state when worker doesn't respond to ping."""
        # Mock inspector with no ping response
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = None

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is False
        assert health["active_tasks"] is None
        assert health["queue_length"] is None
        assert health["scheduled_tasks"] is None
        assert health["last_heartbeat"] is None
        assert health["status"] == "down"

    @patch('app.services.celery_health.celery_app')
    def test_down_state_timeout(self, mock_celery_app):
        """Test down state when inspector times out."""
        from celery.exceptions import TimeoutError as CeleryTimeoutError

        # Mock inspector that raises timeout
        mock_inspect = MagicMock()
        mock_inspect.ping.side_effect = CeleryTimeoutError("Worker did not respond")

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is False
        assert health["status"] == "down"

    @patch('app.services.celery_health.celery_app')
    def test_down_state_exception(self, mock_celery_app):
        """Test down state when inspector raises unexpected exception."""
        # Mock inspector that raises exception
        mock_inspect = MagicMock()
        mock_inspect.ping.side_effect = Exception("Connection refused")

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is False
        assert health["status"] == "down"
        assert "error" in health

    @patch('app.services.celery_health.celery_app')
    def test_multiple_workers(self, mock_celery_app):
        """Test health check with multiple workers."""
        # Mock inspector with 2 workers
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {
            "worker1@hostname": {"ok": "pong"},
            "worker2@hostname": {"ok": "pong"}
        }
        mock_inspect.active.return_value = {
            "worker1@hostname": [{"id": "task1"}],
            "worker2@hostname": [{"id": "task2"}, {"id": "task3"}]
        }
        mock_inspect.reserved.return_value = {
            "worker1@hostname": [{"id": "task1"}],
            "worker2@hostname": [{"id": "task2"}, {"id": "task3"}]
        }
        mock_inspect.scheduled.return_value = {
            "worker1@hostname": [],
            "worker2@hostname": []
        }
        mock_inspect.stats.return_value = {
            "worker1@hostname": {"clock": datetime.now(timezone.utc).timestamp()},
            "worker2@hostname": {"clock": datetime.now(timezone.utc).timestamp()}
        }

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is True
        assert health["active_tasks"] == 3  # Sum across workers
        assert health["queue_length"] == 3
        assert health["status"] == "healthy"

    @patch('app.services.celery_health.celery_app')
    def test_empty_worker_responses(self, mock_celery_app):
        """Test health check when workers return empty data."""
        # Mock inspector with empty responses
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {"worker1@hostname": {"ok": "pong"}}
        mock_inspect.active.return_value = {}
        mock_inspect.reserved.return_value = {}
        mock_inspect.scheduled.return_value = {}
        mock_inspect.stats.return_value = {}

        mock_celery_app.control.inspect.return_value = mock_inspect

        # Execute
        health = get_celery_health(timeout=5)

        # Assert
        assert health["worker_alive"] is True
        assert health["active_tasks"] == 0
        assert health["queue_length"] == 0
        assert health["scheduled_tasks"] == 0
        assert health["last_heartbeat"] is None  # No stats
        assert health["status"] == "healthy"


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_API_TESTS"),
    reason="Live API tests disabled. Set RUN_LIVE_API_TESTS=1 to run.",
)
class TestCeleryHealthAPIEndpoint:
    """Test suite for /api/interactions/health/celery endpoint (requires running server)."""

    def test_health_endpoint_returns_status(self, client):
        """Test that health endpoint returns Celery status."""
        # No auth required for health endpoint
        response = client.get("/api/interactions/health/celery")

        # Should return 200 even if Celery is down (monitoring endpoint)
        assert response.status_code == 200

        # Check response structure
        data = response.json()
        assert "worker_alive" in data
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "down")

    @patch('app.services.celery_health.celery_app')
    def test_health_endpoint_healthy(self, mock_celery_app, client):
        """Test health endpoint returns healthy state."""
        # Mock healthy Celery
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = {"worker1@hostname": {"ok": "pong"}}
        mock_inspect.active.return_value = {"worker1@hostname": []}
        mock_inspect.reserved.return_value = {"worker1@hostname": []}
        mock_inspect.scheduled.return_value = {"worker1@hostname": []}
        mock_inspect.stats.return_value = {"worker1@hostname": {"clock": datetime.now(timezone.utc).timestamp()}}

        mock_celery_app.control.inspect.return_value = mock_inspect

        response = client.get("/api/interactions/health/celery")

        assert response.status_code == 200
        data = response.json()
        assert data["worker_alive"] is True
        assert data["status"] == "healthy"

    @patch('app.services.celery_health.celery_app')
    def test_health_endpoint_down(self, mock_celery_app, client):
        """Test health endpoint returns down state."""
        # Mock down Celery
        mock_inspect = MagicMock()
        mock_inspect.ping.return_value = None

        mock_celery_app.control.inspect.return_value = mock_inspect

        response = client.get("/api/interactions/health/celery")

        assert response.status_code == 200  # Endpoint still returns 200
        data = response.json()
        assert data["worker_alive"] is False
        assert data["status"] == "down"


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_API_TESTS"),
    reason="Live API tests disabled. Set RUN_LIVE_API_TESTS=1 to run.",
)
class TestCeleryHealthInOpsAlerts:
    """Test suite for Celery health integration in ops-alerts (requires running server)."""

    @patch('app.services.interaction_metrics.get_celery_health')
    def test_ops_alerts_includes_celery_down(self, mock_get_celery_health, client, auth_token):
        """Test that ops-alerts includes Celery down alert."""
        # Mock Celery down
        mock_get_celery_health.return_value = {
            "worker_alive": False,
            "status": "down",
            "active_tasks": None,
            "queue_length": None,
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/interactions/metrics/ops-alerts", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Check alert exists
        alerts = data.get("alerts", [])
        celery_alerts = [a for a in alerts if a.get("code") == "celery_worker_down"]
        assert len(celery_alerts) == 1
        assert celery_alerts[0]["severity"] == "critical"

    @patch('app.services.interaction_metrics.get_celery_health')
    def test_ops_alerts_includes_celery_degraded(self, mock_get_celery_health, client, auth_token):
        """Test that ops-alerts includes Celery degraded alert."""
        # Mock Celery degraded
        mock_get_celery_health.return_value = {
            "worker_alive": True,
            "status": "degraded",
            "active_tasks": 10,
            "queue_length": 150,
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/interactions/metrics/ops-alerts", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Check alert exists
        alerts = data.get("alerts", [])
        celery_alerts = [a for a in alerts if a.get("code") == "celery_queue_high"]
        assert len(celery_alerts) == 1
        assert celery_alerts[0]["severity"] == "medium"

    @patch('app.services.interaction_metrics.get_celery_health')
    def test_ops_alerts_no_celery_alert_when_healthy(self, mock_get_celery_health, client, auth_token):
        """Test that ops-alerts has no Celery alert when healthy."""
        # Mock Celery healthy
        mock_get_celery_health.return_value = {
            "worker_alive": True,
            "status": "healthy",
            "active_tasks": 5,
            "queue_length": 10,
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/interactions/metrics/ops-alerts", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Check no Celery alerts
        alerts = data.get("alerts", [])
        celery_alerts = [a for a in alerts if a.get("code") in ("celery_worker_down", "celery_queue_high")]
        assert len(celery_alerts) == 0

    @patch('app.services.interaction_metrics.get_celery_health')
    def test_ops_alerts_includes_celery_health_payload(self, mock_get_celery_health, client, auth_token):
        """Test that ops-alerts includes celery_health in response payload."""
        # Mock Celery healthy
        mock_celery_health = {
            "worker_alive": True,
            "status": "healthy",
            "active_tasks": 3,
            "queue_length": 5,
            "scheduled_tasks": 0,
            "last_heartbeat": datetime.now(timezone.utc),
        }
        mock_get_celery_health.return_value = mock_celery_health

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/interactions/metrics/ops-alerts", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Check celery_health is in response
        assert "celery_health" in data
        assert data["celery_health"]["worker_alive"] is True
        assert data["celery_health"]["status"] == "healthy"
