"""
AgentIQ Load Testing with Locust

Tests the Chat Center backend API under load to identify performance bottlenecks
and validate that p95 latency stays under acceptable thresholds.

Environment variables:
- LOAD_TEST_EMAIL: Test user email (required)
- LOAD_TEST_PASSWORD: Test user password (required)
- LOAD_TEST_HOST: API host (default: http://localhost:8001)

Usage:
    # Interactive UI mode
    locust -f locustfile.py --host=http://localhost:8001

    # Headless mode
    locust -f locustfile.py --host=http://localhost:8001 \
        --users=100 --spawn-rate=10 --run-time=5m --headless

    # Against staging
    locust -f locustfile.py --host=https://agentiq.ru/api \
        --users=50 --spawn-rate=5 --run-time=3m --headless
"""

import os
import random
from locust import HttpUser, task, between, events
from locust.exception import StopUser
import logging

logger = logging.getLogger(__name__)


class AgentIQUser(HttpUser):
    """
    Simulates an authenticated user interacting with the AgentIQ Chat Center API.

    Weight distribution:
    - List operations: 60% (most common: browsing chats, interactions)
    - Detail operations: 20% (viewing individual items)
    - Analytics: 15% (metrics, quality reports)
    - Write operations: 5% (generating drafts, syncing data)
    """

    # Wait 1-3 seconds between tasks (realistic user behavior)
    wait_time = between(1, 3)

    # Shared state for interaction IDs
    interaction_ids = []
    chat_ids = []

    def on_start(self):
        """
        Called when a simulated user starts.
        Authenticates and caches interaction/chat IDs for detail views.
        """
        # Get credentials from environment
        email = os.getenv("LOAD_TEST_EMAIL")
        password = os.getenv("LOAD_TEST_PASSWORD")

        if not email or not password:
            logger.error("LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD must be set")
            raise StopUser()

        # Login and get JWT token
        response = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })

        if response.status_code != 200:
            logger.error(f"Login failed: {response.status_code} - {response.text}")
            raise StopUser()

        data = response.json()
        self.token = data["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        logger.info(f"User authenticated: {email}")

        # Pre-fetch some interaction IDs for detail views
        self._cache_interaction_ids()
        self._cache_chat_ids()

    def _cache_interaction_ids(self):
        """Fetch and cache interaction IDs for detail view tests."""
        response = self.client.get(
            "/api/interactions",
            params={"page": 1, "page_size": 20, "include_total": False},
            headers=self.headers,
            name="/api/interactions (cache)"
        )

        if response.status_code == 200:
            data = response.json()
            interactions = data.get("interactions", [])
            AgentIQUser.interaction_ids = [item["id"] for item in interactions if item.get("id")]
            logger.info(f"Cached {len(AgentIQUser.interaction_ids)} interaction IDs")

    def _cache_chat_ids(self):
        """Fetch and cache chat IDs for detail view tests."""
        response = self.client.get(
            "/api/chats",
            params={"page": 1, "page_size": 20},
            headers=self.headers,
            name="/api/chats (cache)"
        )

        if response.status_code == 200:
            data = response.json()
            chats = data.get("chats", [])
            AgentIQUser.chat_ids = [item["id"] for item in chats if item.get("id")]
            logger.info(f"Cached {len(AgentIQUser.chat_ids)} chat IDs")

    # ========== LIST OPERATIONS (60% weight) ==========

    @task(20)
    def list_interactions_all(self):
        """GET /api/interactions - List all interactions (most common operation)."""
        self.client.get(
            "/api/interactions",
            params={
                "page": random.randint(1, 3),
                "page_size": 50,
                "include_total": False  # Faster without count
            },
            headers=self.headers,
            name="/api/interactions?channel=all"
        )

    @task(15)
    def list_interactions_review(self):
        """GET /api/interactions?channel=review - Filter by reviews."""
        self.client.get(
            "/api/interactions",
            params={
                "channel": "review",
                "page": 1,
                "page_size": 50,
                "include_total": False
            },
            headers=self.headers,
            name="/api/interactions?channel=review"
        )

    @task(10)
    def list_interactions_question(self):
        """GET /api/interactions?channel=question - Filter by questions."""
        self.client.get(
            "/api/interactions",
            params={
                "channel": "question",
                "page": 1,
                "page_size": 50,
                "include_total": False
            },
            headers=self.headers,
            name="/api/interactions?channel=question"
        )

    @task(10)
    def list_interactions_chat(self):
        """GET /api/interactions?channel=chat - Filter by chats."""
        self.client.get(
            "/api/interactions",
            params={
                "channel": "chat",
                "page": 1,
                "page_size": 50,
                "include_total": False
            },
            headers=self.headers,
            name="/api/interactions?channel=chat"
        )

    @task(5)
    def list_chats(self):
        """GET /api/chats - List chats (legacy endpoint)."""
        self.client.get(
            "/api/chats",
            params={
                "page": 1,
                "page_size": 50
            },
            headers=self.headers,
            name="/api/chats"
        )

    # ========== DETAIL OPERATIONS (20% weight) ==========

    @task(10)
    def get_interaction_detail(self):
        """GET /api/interactions/{id} - View single interaction."""
        if not AgentIQUser.interaction_ids:
            return

        interaction_id = random.choice(AgentIQUser.interaction_ids)
        self.client.get(
            f"/api/interactions/{interaction_id}",
            headers=self.headers,
            name="/api/interactions/{id}"
        )

    @task(5)
    def get_interaction_timeline(self):
        """GET /api/interactions/{id}/timeline - View interaction timeline."""
        if not AgentIQUser.interaction_ids:
            return

        interaction_id = random.choice(AgentIQUser.interaction_ids)
        self.client.get(
            f"/api/interactions/{interaction_id}/timeline",
            params={"max_items": 100, "product_window_days": 45},
            headers=self.headers,
            name="/api/interactions/{id}/timeline"
        )

    @task(5)
    def get_chat_detail(self):
        """GET /api/chats/{id} - View single chat."""
        if not AgentIQUser.chat_ids:
            return

        chat_id = random.choice(AgentIQUser.chat_ids)
        self.client.get(
            f"/api/chats/{chat_id}",
            headers=self.headers,
            name="/api/chats/{id}"
        )

    # ========== ANALYTICS OPERATIONS (15% weight) ==========

    @task(6)
    def get_quality_metrics(self):
        """GET /api/interactions/metrics/quality - Quality metrics dashboard."""
        self.client.get(
            "/api/interactions/metrics/quality",
            params={"days": 30, "channel": None},
            headers=self.headers,
            name="/api/interactions/metrics/quality"
        )

    @task(5)
    def get_quality_history(self):
        """GET /api/interactions/metrics/quality-history - Quality trend chart."""
        self.client.get(
            "/api/interactions/metrics/quality-history",
            params={"days": 30, "channel": None},
            headers=self.headers,
            name="/api/interactions/metrics/quality-history"
        )

    @task(2)
    def get_ops_alerts(self):
        """GET /api/interactions/metrics/ops-alerts - Operational alerts."""
        self.client.get(
            "/api/interactions/metrics/ops-alerts",
            headers=self.headers,
            name="/api/interactions/metrics/ops-alerts"
        )

    @task(2)
    def get_pilot_readiness(self):
        """GET /api/interactions/metrics/pilot-readiness - Pilot readiness check."""
        self.client.get(
            "/api/interactions/metrics/pilot-readiness",
            params={
                "max_sync_age_minutes": 30,
                "max_overdue_questions": 0,
                "max_manual_rate": 0.6,
                "max_open_backlog": 250
            },
            headers=self.headers,
            name="/api/interactions/metrics/pilot-readiness"
        )

    # ========== WRITE OPERATIONS (5% weight) - Lower frequency ==========

    @task(2)
    def generate_ai_draft(self):
        """POST /api/interactions/{id}/ai-draft - Generate AI response draft."""
        if not AgentIQUser.interaction_ids:
            return

        interaction_id = random.choice(AgentIQUser.interaction_ids)
        self.client.post(
            f"/api/interactions/{interaction_id}/ai-draft",
            json={"force_regenerate": False},
            headers=self.headers,
            name="/api/interactions/{id}/ai-draft"
        )

    @task(1)
    def sync_reviews(self):
        """POST /api/interactions/sync/reviews - Trigger review sync (expensive)."""
        self.client.post(
            "/api/interactions/sync/reviews",
            params={
                "only_unanswered": True,
                "max_items": 50,  # Small batch for load test
                "page_size": 50
            },
            headers=self.headers,
            name="/api/interactions/sync/reviews"
        )

    @task(1)
    def sync_questions(self):
        """POST /api/interactions/sync/questions - Trigger question sync (expensive)."""
        self.client.post(
            "/api/interactions/sync/questions",
            params={
                "only_unanswered": True,
                "max_items": 50,  # Small batch for load test
                "page_size": 50
            },
            headers=self.headers,
            name="/api/interactions/sync/questions"
        )

    @task(1)
    def sync_chats(self):
        """POST /api/interactions/sync/chats - Trigger chat sync (expensive)."""
        self.client.post(
            "/api/interactions/sync/chats",
            params={
                "max_items": 50,  # Small batch for load test
                "direct_wb_fetch": False
            },
            headers=self.headers,
            name="/api/interactions/sync/chats"
        )


# ========== CUSTOM METRICS AND VALIDATION ==========

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the load test starts."""
    logger.info("=" * 60)
    logger.info("AgentIQ Load Test Started")
    logger.info("=" * 60)
    logger.info(f"Host: {environment.host}")
    logger.info(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Called when the load test stops.
    Validates performance metrics against thresholds.
    """
    logger.info("=" * 60)
    logger.info("AgentIQ Load Test Finished")
    logger.info("=" * 60)

    stats = environment.stats
    total_stats = stats.total

    # Print summary
    logger.info(f"Total Requests: {total_stats.num_requests}")
    logger.info(f"Total Failures: {total_stats.num_failures}")
    logger.info(f"Median Response Time: {total_stats.median_response_time}ms")
    logger.info(f"95th Percentile: {total_stats.get_response_time_percentile(0.95)}ms")
    logger.info(f"99th Percentile: {total_stats.get_response_time_percentile(0.99)}ms")
    logger.info(f"Average Response Time: {total_stats.avg_response_time:.2f}ms")
    logger.info(f"Requests/sec: {total_stats.total_rps:.2f}")

    # Calculate error rate
    error_rate = total_stats.num_failures / total_stats.num_requests if total_stats.num_requests > 0 else 0
    logger.info(f"Error Rate: {error_rate * 100:.2f}%")

    # Performance thresholds
    p95 = total_stats.get_response_time_percentile(0.95)

    logger.info("=" * 60)
    logger.info("PERFORMANCE VALIDATION")
    logger.info("=" * 60)

    # Target: p95 < 500ms for healthy system, < 1000ms for acceptable
    if p95 < 500:
        logger.info(f"✓ p95 ({p95}ms) < 500ms - EXCELLENT")
        p95_status = "PASS"
    elif p95 < 1000:
        logger.warning(f"⚠ p95 ({p95}ms) < 1000ms - ACCEPTABLE")
        p95_status = "PASS"
    else:
        logger.error(f"✗ p95 ({p95}ms) >= 1000ms - FAILED")
        p95_status = "FAIL"
        environment.process_exit_code = 1

    # Target: error rate < 1% for healthy, < 5% for acceptable
    if error_rate < 0.01:
        logger.info(f"✓ Error rate ({error_rate * 100:.2f}%) < 1% - EXCELLENT")
        error_status = "PASS"
    elif error_rate < 0.05:
        logger.warning(f"⚠ Error rate ({error_rate * 100:.2f}%) < 5% - ACCEPTABLE")
        error_status = "PASS"
    else:
        logger.error(f"✗ Error rate ({error_rate * 100:.2f}%) >= 5% - FAILED")
        error_status = "FAIL"
        environment.process_exit_code = 1

    logger.info("=" * 60)
    logger.info(f"FINAL RESULT: {'PASS' if p95_status == 'PASS' and error_status == 'PASS' else 'FAIL'}")
    logger.info("=" * 60)
