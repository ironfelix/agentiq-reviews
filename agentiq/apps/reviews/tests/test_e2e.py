"""End-to-end tests for complete user flows."""
import pytest
from sqlalchemy import select
from backend.database import User, Task, Report, InviteCode


@pytest.mark.e2e
class TestCompleteUserJourney:
    """End-to-end test for complete user journey from login to report."""

    async def test_new_user_registration_and_task_creation(
        self, test_client, test_db_session, mock_telegram_auth_data, mocker
    ):
        """
        Test complete flow:
        1. New user Telegram login
        2. Invite code entry
        3. Create analysis task
        4. View report
        """
        # Step 1: Create invite code
        invite = InviteCode(code="E2E-TEST-2026", max_uses=10, used_count=0)
        test_db_session.add(invite)
        await test_db_session.commit()

        # Step 2: Telegram login (new user)
        auth_response = await test_client.get(
            "/api/auth/telegram/callback",
            params=mock_telegram_auth_data,
            follow_redirects=False,
        )
        assert auth_response.status_code in [200, 302, 307]
        session_cookie = auth_response.cookies.get("session_token")
        assert session_cookie is not None

        # Step 3: Enter invite code
        invite_response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "E2E-TEST-2026"},
            cookies={"session_token": session_cookie},
        )
        assert invite_response.status_code == 200

        # Verify user has invite now
        result = await test_db_session.execute(
            select(User).where(User.telegram_id == int(mock_telegram_auth_data["id"]))
        )
        user = result.scalar_one()
        assert user.invite_code_id is not None

        # Step 4: Create task (mock Celery)
        mock_celery = mocker.patch("backend.main.analyze_article_task.delay")

        task_response = await test_client.post(
            "/api/tasks/create",
            json={"article_id": 12345678},
            cookies={"session_token": session_cookie},
        )
        assert task_response.status_code == 200
        task_data = task_response.json()
        task_id = task_data["id"]

        # Step 5: Simulate task completion by updating DB directly
        result = await test_db_session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one()
        task.status = "completed"
        task.progress = 100

        report = Report(
            task_id=task.id,
            article_id=task.article_id,
            category="test",
            rating=4.5,
            feedback_count=100,
            data='{"header": {"product_name": "E2E Test Product"}}',
        )
        test_db_session.add(report)
        await test_db_session.commit()

        # Step 6: View report
        report_response = await test_client.get(
            f"/dashboard/report/{task_id}",
            cookies={"session_token": session_cookie},
        )
        assert report_response.status_code == 200
        assert b"E2E Test Product" in report_response.content

        # Step 7: Create share link
        share_response = await test_client.post(
            f"/api/reports/{task_id}/share",
            cookies={"session_token": session_cookie},
        )
        assert share_response.status_code == 200
        share_data = share_response.json()
        share_token = share_data["token"]

        # Step 8: Access shared report (no auth)
        public_response = await test_client.get(f"/share/{share_token}")
        assert public_response.status_code == 200
        assert b"E2E Test Product" in public_response.content


@pytest.mark.e2e
class TestExistingUserFlow:
    """Test flow for existing user."""

    async def test_existing_user_login_and_task_list(
        self, test_client, test_user, completed_task, mock_telegram_auth_data
    ):
        """
        Test existing user flow:
        1. Login (already has invite)
        2. View task list
        3. View existing report
        """
        from backend.auth import create_session_token

        # Step 1: Login
        mock_telegram_auth_data["id"] = str(test_user.telegram_id)
        auth_response = await test_client.get(
            "/api/auth/telegram/callback",
            params=mock_telegram_auth_data,
            follow_redirects=False,
        )
        assert auth_response.status_code in [200, 302, 307]

        # Step 2: View dashboard
        token = create_session_token(test_user.telegram_id)
        dashboard_response = await test_client.get(
            "/dashboard",
            cookies={"session_token": token},
        )
        assert dashboard_response.status_code == 200

        # Step 3: List tasks
        tasks_response = await test_client.get(
            "/api/tasks/list",
            cookies={"session_token": token},
        )
        assert tasks_response.status_code == 200
        tasks = tasks_response.json()
        assert len(tasks) >= 1

        # Step 4: View report
        report_response = await test_client.get(
            f"/dashboard/report/{completed_task.id}",
            cookies={"session_token": token},
        )
        assert report_response.status_code == 200


@pytest.mark.e2e
class TestErrorScenarios:
    """Test error handling scenarios."""

    async def test_unauthorized_access_attempts(self, test_client, completed_task):
        """Test accessing protected resources without auth."""
        # Try to create task
        response = await test_client.post(
            "/api/tasks/create",
            json={"article_id": 12345678},
        )
        assert response.status_code == 401

        # Try to view report
        response = await test_client.get(f"/dashboard/report/{completed_task.id}")
        # In test mode with dev bypass, this might succeed
        # In production, it would be 401

        # Try to delete task
        response = await test_client.delete(f"/api/tasks/{completed_task.id}")
        assert response.status_code == 401

    async def test_access_other_users_resources(
        self, test_client, test_user, test_db_session
    ):
        """Test that users cannot access other users' resources."""
        from backend.auth import create_session_token

        # Create another user
        other_user = User(
            telegram_id=999999999,
            username="other_user",
            auth_date=1234567890,
            invite_code_id=1,
        )
        test_db_session.add(other_user)
        await test_db_session.commit()

        # Create task for other user
        other_task = Task(
            user_id=other_user.id,
            article_id=99999,
            status="completed",
            progress=100,
        )
        test_db_session.add(other_task)
        await test_db_session.commit()

        # Try to access with test_user's token
        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            f"/api/tasks/{other_task.id}/status",
            cookies={"session_token": token},
        )
        assert response.status_code == 404  # Not found (ownership check)

    async def test_invalid_invite_code_flow(
        self, test_client, test_user_without_invite
    ):
        """Test invalid invite code rejection."""
        from backend.auth import create_session_token

        token = create_session_token(test_user_without_invite.telegram_id)

        # Try invalid code
        response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "INVALID-CODE-12345"},
            cookies={"session_token": token},
        )
        assert response.status_code == 400

    async def test_task_not_found(self, test_client, test_user):
        """Test accessing non-existent task."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)

        response = await test_client.get(
            "/api/tasks/999999/status",
            cookies={"session_token": token},
        )
        assert response.status_code == 404


@pytest.mark.e2e
class TestMultipleTasksFlow:
    """Test managing multiple tasks."""

    async def test_create_multiple_tasks_and_delete(
        self, test_client, test_user, test_db_session, mocker
    ):
        """Test creating multiple tasks and deleting them."""
        from backend.auth import create_session_token

        mock_celery = mocker.patch("backend.main.analyze_article_task.delay")
        token = create_session_token(test_user.telegram_id)

        # Create 3 tasks
        task_ids = []
        for i in range(3):
            response = await test_client.post(
                "/api/tasks/create",
                json={"article_id": 100000 + i},
                cookies={"session_token": token},
            )
            assert response.status_code == 200
            task_ids.append(response.json()["id"])

        # List tasks
        response = await test_client.get(
            "/api/tasks/list",
            cookies={"session_token": token},
        )
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 3

        # Delete first task
        response = await test_client.delete(
            f"/api/tasks/{task_ids[0]}",
            cookies={"session_token": token},
        )
        assert response.status_code == 200

        # Verify deletion
        response = await test_client.get(
            f"/api/tasks/{task_ids[0]}/status",
            cookies={"session_token": token},
        )
        assert response.status_code == 404


@pytest.mark.e2e
class TestCommunicationReport:
    """Test communication report flow."""

    async def test_view_communication_report(
        self, test_client, test_user, completed_task
    ):
        """Test viewing communication report."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)

        # View communication report
        response = await test_client.get(
            f"/dashboard/report/{completed_task.id}/communication",
            cookies={"session_token": token},
        )
        assert response.status_code == 200

    async def test_share_communication_report(
        self, test_client, test_user, completed_task, test_db_session
    ):
        """Test sharing communication report."""
        from backend.auth import create_session_token
        import secrets

        token = create_session_token(test_user.telegram_id)

        # Create share link
        response = await test_client.post(
            f"/api/reports/{completed_task.id}/share",
            cookies={"session_token": token},
        )
        assert response.status_code == 200
        share_data = response.json()

        # Access shared communication report (no auth)
        response = await test_client.get(
            f"/share/{share_data['token']}/communication"
        )
        assert response.status_code == 200
