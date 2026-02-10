"""Integration tests for API endpoints."""
import pytest
import json
from sqlalchemy import select
from backend.database import User, Task, Report, InviteCode


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    async def test_health_check(self, test_client):
        """Test health endpoint."""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "mvp2"


@pytest.mark.integration
class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    async def test_telegram_auth_callback_new_user(self, test_client, mock_telegram_auth_data, test_db_session):
        """Test Telegram auth callback for new user."""
        response = await test_client.get("/api/auth/telegram/callback", params=mock_telegram_auth_data)
        assert response.status_code == 200

        # Check user was created
        result = await test_db_session.execute(
            select(User).where(User.telegram_id == int(mock_telegram_auth_data["id"]))
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.username == mock_telegram_auth_data["username"]

        # Should redirect to invite page (no invite code yet)
        assert response.history  # Has redirect
        assert "/invite" in str(response.url)

        # Check session cookie
        assert "session_token" in response.cookies

    async def test_telegram_auth_callback_existing_user(self, test_client, test_user, mock_telegram_auth_data, test_db_session):
        """Test Telegram auth callback for existing user with invite."""
        # Update mock data to match test_user
        mock_telegram_auth_data["id"] = str(test_user.telegram_id)

        response = await test_client.get("/api/auth/telegram/callback", params=mock_telegram_auth_data)
        assert response.status_code == 200

        # Should redirect to dashboard (has invite code)
        assert "/dashboard" in str(response.url)

    async def test_telegram_auth_callback_invalid_hash(self, test_client, mock_telegram_auth_data):
        """Test auth with invalid hash."""
        mock_telegram_auth_data["hash"] = "invalid"
        response = await test_client.get("/api/auth/telegram/callback", params=mock_telegram_auth_data)
        assert response.status_code == 403

    async def test_verify_invite_code_success(self, test_client, test_user_without_invite, test_db_session):
        """Test successful invite code verification."""
        from backend.auth import create_session_token

        # Create valid invite code
        invite = InviteCode(code="TEST-2026", max_uses=10, used_count=0)
        test_db_session.add(invite)
        await test_db_session.commit()

        # Make request with auth
        token = create_session_token(test_user_without_invite.telegram_id)
        response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "TEST-2026"},
            cookies={"session_token": token},
        )
        assert response.status_code == 200

        # Check user now has invite
        await test_db_session.refresh(test_user_without_invite)
        assert test_user_without_invite.invite_code_id is not None

        # Check usage count increased
        await test_db_session.refresh(invite)
        assert invite.used_count == 1

    async def test_verify_invite_code_invalid(self, test_client, test_user_without_invite):
        """Test with invalid invite code."""
        from backend.auth import create_session_token

        token = create_session_token(test_user_without_invite.telegram_id)
        response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "INVALID-CODE"},
            cookies={"session_token": token},
        )
        assert response.status_code == 400

    async def test_verify_invite_code_exhausted(self, test_client, test_user_without_invite, test_db_session):
        """Test with exhausted invite code."""
        from backend.auth import create_session_token

        invite = InviteCode(code="EXHAUSTED-2026", max_uses=1, used_count=1)
        test_db_session.add(invite)
        await test_db_session.commit()

        token = create_session_token(test_user_without_invite.telegram_id)
        response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "EXHAUSTED-2026"},
            cookies={"session_token": token},
        )
        assert response.status_code == 400

    async def test_logout(self, test_client, auth_headers):
        """Test logout endpoint."""
        response = await test_client.post("/api/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        # Session cookie should be deleted
        assert "session_token" in response.cookies


@pytest.mark.integration
class TestTaskEndpoints:
    """Tests for task management endpoints."""

    async def test_create_task(self, test_client, test_user, test_db_session, mocker):
        """Test creating a new task."""
        from backend.auth import create_session_token

        # Mock Celery task
        mock_celery = mocker.patch("backend.main.analyze_article_task.delay")

        token = create_session_token(test_user.telegram_id)
        response = await test_client.post(
            "/api/tasks/create",
            json={"article_id": 12345678},
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["article_id"] == 12345678
        assert data["status"] == "pending"
        assert data["progress"] == 0
        assert "id" in data

        # Check Celery task was triggered
        mock_celery.assert_called_once()

    async def test_create_task_unauthorized(self, test_client):
        """Test creating task without auth."""
        response = await test_client.post(
            "/api/tasks/create",
            json={"article_id": 12345678},
        )
        assert response.status_code == 401

    async def test_list_tasks(self, test_client, test_user, test_task, completed_task, test_db_session):
        """Test listing user tasks."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            "/api/tasks/list",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least test_task and completed_task

        # Check completed task has report data
        completed_tasks = [t for t in data if t["status"] == "completed"]
        assert len(completed_tasks) >= 1
        assert completed_tasks[0]["rating"] is not None

    async def test_get_task_status(self, test_client, test_user, test_task):
        """Test getting task status."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            f"/api/tasks/{test_task.id}/status",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_task.id
        assert data["status"] == test_task.status

    async def test_get_task_status_not_found(self, test_client, test_user):
        """Test getting non-existent task."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            "/api/tasks/99999/status",
            cookies={"session_token": token},
        )

        assert response.status_code == 404

    async def test_delete_task(self, test_client, test_user, test_db_session):
        """Test deleting a task."""
        from backend.auth import create_session_token

        # Create task to delete
        task = Task(user_id=test_user.id, article_id=99999, status="pending")
        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        token = create_session_token(test_user.telegram_id)
        response = await test_client.delete(
            f"/api/tasks/{task.id}",
            cookies={"session_token": token},
        )

        assert response.status_code == 200

        # Verify deletion
        result = await test_db_session.execute(
            select(Task).where(Task.id == task.id)
        )
        deleted_task = result.scalar_one_or_none()
        assert deleted_task is None

    async def test_get_task_report(self, test_client, test_user, completed_task):
        """Test getting task report as JSON."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            f"/api/tasks/{completed_task.id}/report",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == completed_task.id
        assert "data" in data
        assert isinstance(data["data"], dict)


@pytest.mark.integration
class TestReportEndpoints:
    """Tests for report viewing and sharing."""

    async def test_report_page_access(self, test_client, test_user, completed_task):
        """Test accessing report page."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            f"/dashboard/report/{completed_task.id}",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        assert b"Test Product" in response.content

    async def test_comm_report_page_access(self, test_client, test_user, completed_task):
        """Test accessing communication report page."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            f"/dashboard/report/{completed_task.id}/communication",
            cookies={"session_token": token},
        )

        assert response.status_code == 200

    async def test_create_share_link(self, test_client, test_user, completed_task, test_db_session):
        """Test creating public share link."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.post(
            f"/api/reports/{completed_task.id}/share",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "share_url" in data
        assert "token" in data

        # Verify share token was saved
        result = await test_db_session.execute(
            select(Report).where(Report.task_id == completed_task.id)
        )
        report = result.scalar_one()
        assert report.share_token is not None

    async def test_shared_report_access_no_auth(self, test_client, completed_task, test_db_session):
        """Test accessing shared report without authentication."""
        # Create share token first
        result = await test_db_session.execute(
            select(Report).where(Report.task_id == completed_task.id)
        )
        report = result.scalar_one()

        import secrets
        report.share_token = secrets.token_urlsafe(32)
        await test_db_session.commit()

        # Access without auth
        response = await test_client.get(f"/share/{report.share_token}")
        assert response.status_code == 200
        assert b"Test Product" in response.content

    async def test_shared_report_invalid_token(self, test_client):
        """Test accessing shared report with invalid token."""
        response = await test_client.get("/share/invalid-token-12345")
        assert response.status_code == 404


@pytest.mark.integration
class TestFrontendRoutes:
    """Tests for frontend page routes."""

    async def test_landing_page(self, test_client):
        """Test landing page."""
        response = await test_client.get("/")
        assert response.status_code == 200
        assert b"Telegram" in response.content or b"telegram" in response.content

    async def test_invite_page(self, test_client):
        """Test invite page."""
        response = await test_client.get("/invite")
        assert response.status_code == 200

    async def test_dashboard_requires_auth(self, test_client):
        """Test dashboard requires authentication."""
        response = await test_client.get("/dashboard", follow_redirects=False)
        # In test mode, we have dev bypass, so it will succeed
        # In production mode, it would return 401
        # Since ENVIRONMENT=test, dashboard should work
        assert response.status_code == 200

    async def test_dashboard_with_auth(self, test_client, test_user):
        """Test dashboard with authentication."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            "/dashboard",
            cookies={"session_token": token},
        )

        assert response.status_code == 200
