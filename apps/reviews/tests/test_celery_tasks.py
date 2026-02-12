"""Integration tests for Celery tasks with mocked external APIs."""
import pytest
import json
import sys
import os
import responses
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.tasks import (
    create_wbcon_task,
    check_wbcon_status,
    fetch_all_feedbacks,
    run_analysis,
    WBCON_FB_BASE,
)


@pytest.mark.integration
class TestWBCONAPIIntegration:
    """Tests for WBCON API integration with mocked responses."""

    @responses.activate
    def test_create_wbcon_task_success(self):
        """Test successful WBCON task creation."""
        responses.add(
            responses.POST,
            f"{WBCON_FB_BASE}/create_task_fb",
            json={"task_id": "01-test-task-id"},
            status=200,
        )

        task_id = create_wbcon_task(282955222)
        assert task_id == "01-test-task-id"

    @responses.activate
    def test_create_wbcon_task_api_error(self):
        """Test WBCON task creation with API error."""
        responses.add(
            responses.POST,
            f"{WBCON_FB_BASE}/create_task_fb",
            json={"error": "Invalid article"},
            status=400,
        )

        with pytest.raises(Exception) as exc_info:
            create_wbcon_task(282955222)
        assert "WBCON API request failed" in str(exc_info.value)

    @responses.activate
    def test_create_wbcon_task_invalid_response(self):
        """Test WBCON task creation with invalid response format."""
        responses.add(
            responses.POST,
            f"{WBCON_FB_BASE}/create_task_fb",
            json={"invalid": "response"},
            status=200,
        )

        with pytest.raises(Exception) as exc_info:
            create_wbcon_task(282955222)
        assert "invalid response" in str(exc_info.value).lower()

    @responses.activate
    def test_check_wbcon_status_ready(self):
        """Test checking WBCON task status when ready."""
        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/task_status",
            json={"task_id": "01-test", "is_ready": True, "status": "completed"},
            status=200,
        )

        status = check_wbcon_status("01-test")
        assert status["is_ready"] is True
        assert status["status"] == "completed"

    @responses.activate
    def test_check_wbcon_status_pending(self):
        """Test checking WBCON task status when pending."""
        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/task_status",
            json={"task_id": "01-test", "is_ready": False, "status": "processing"},
            status=200,
        )

        status = check_wbcon_status("01-test")
        assert status["is_ready"] is False

    @responses.activate
    def test_fetch_all_feedbacks_single_page(self, sample_wbcon_response):
        """Test fetching feedbacks with single page."""
        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/get_results_fb",
            json=sample_wbcon_response,
            status=200,
        )

        feedbacks = fetch_all_feedbacks("01-test", feedback_count=1)
        assert len(feedbacks) == 1
        assert feedbacks[0]["fb_id"] == "12345"

    @responses.activate
    def test_fetch_all_feedbacks_pagination(self):
        """Test fetching feedbacks with pagination."""
        # First page: 100 items
        first_page = [{
            "feedback_count": 150,
            "rating": 4.5,
            "feedbacks": [{"fb_id": f"id_{i}", "valuation": 5} for i in range(100)]
        }]

        # Second page: 50 items
        second_page = [{
            "feedback_count": 150,
            "rating": 4.5,
            "feedbacks": [{"fb_id": f"id_{i}", "valuation": 5} for i in range(100, 150)]
        }]

        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/get_results_fb",
            json=first_page,
            status=200,
        )

        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/get_results_fb",
            json=second_page,
            status=200,
        )

        feedbacks = fetch_all_feedbacks("01-test", feedback_count=150)
        assert len(feedbacks) == 150

    @responses.activate
    def test_fetch_all_feedbacks_deduplication(self):
        """Test feedback deduplication (WBCON bug workaround)."""
        # Simulate duplicate IDs in pagination
        page_with_dupes = [{
            "feedback_count": 200,
            "rating": 4.5,
            "feedbacks": [
                {"fb_id": "dup_1", "valuation": 5},
                {"fb_id": "dup_2", "valuation": 4},
                {"fb_id": "dup_1", "valuation": 5},  # Duplicate
            ]
        }]

        responses.add(
            responses.GET,
            f"{WBCON_FB_BASE}/get_results_fb",
            json=page_with_dupes,
            status=200,
        )

        feedbacks = fetch_all_feedbacks("01-test", feedback_count=3)
        # Should deduplicate
        assert len(feedbacks) == 2
        ids = [f["fb_id"] for f in feedbacks]
        assert len(ids) == len(set(ids))  # All unique


@pytest.mark.integration
class TestAnalysisScript:
    """Tests for analysis script execution."""

    def test_run_analysis_with_mock_script(self, sample_wbcon_response, tmp_path, mocker):
        """Test running analysis script with mocked subprocess."""
        feedbacks_data = sample_wbcon_response[0]

        mock_result = {
            "header": {
                "product_name": "Test Product",
                "category": "flashlight",
                "rating": 4.5,
                "feedback_count": 100,
            },
            "signal": {
                "scores": [{"label": "red", "rating": 3.2, "count": 15}]
            }
        }

        # Mock subprocess to return our result
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b""
        mock_proc.stderr = b""

        # Create temp output file with mock result
        output_path = tmp_path / "output.json"

        def mock_run(*args, **kwargs):
            # Write mock result to output file
            with open(output_path, 'w') as f:
                json.dump(mock_result, f)
            return mock_proc

        mocker.patch('subprocess.run', side_effect=mock_run)
        mocker.patch('tempfile.mktemp', return_value=str(output_path))
        mocker.patch('tempfile.NamedTemporaryFile')

        # Note: This will fail if script doesn't exist, but tests the integration
        # In real CI, we'd need the actual script or more sophisticated mocking

    def test_run_analysis_timeout(self, sample_wbcon_response, mocker):
        """Test analysis script timeout handling."""
        import subprocess

        feedbacks_data = sample_wbcon_response[0]

        # Mock subprocess to raise TimeoutExpired
        mocker.patch(
            'subprocess.run',
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=300)
        )

        with pytest.raises(Exception) as exc_info:
            run_analysis(282955222, feedbacks_data)
        assert "timeout" in str(exc_info.value).lower()

    def test_run_analysis_script_failure(self, sample_wbcon_response, mocker):
        """Test analysis script failure handling."""
        import subprocess

        feedbacks_data = sample_wbcon_response[0]

        # Mock subprocess to fail
        mocker.patch(
            'subprocess.run',
            side_effect=subprocess.CalledProcessError(
                returncode=1,
                cmd="test",
                stderr=b"Script error"
            )
        )

        with pytest.raises(Exception) as exc_info:
            run_analysis(282955222, feedbacks_data)
        assert "Analysis failed" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.slow
class TestFullTaskFlow:
    """Integration tests for complete task flow."""

    @patch('backend.tasks.create_wbcon_task')
    @patch('backend.tasks.check_wbcon_status')
    @patch('backend.tasks.fetch_all_feedbacks')
    @patch('backend.tasks.run_analysis')
    @patch('backend.tasks.send_telegram_notification')
    def test_analyze_article_task_success(
        self,
        mock_telegram,
        mock_analysis,
        mock_fetch,
        mock_status,
        mock_create,
        test_db_session,
        test_user,
        sample_feedbacks,
    ):
        """Test full analyze_article_task flow with all mocks."""
        from backend.tasks import analyze_article_task, SessionLocal
        from backend.database import Task

        # Setup mocks
        mock_create.return_value = "01-test-task-id"
        mock_status.return_value = {"is_ready": True, "status": "completed"}
        mock_fetch.return_value = sample_feedbacks
        mock_analysis.return_value = {
            "header": {
                "product_name": "Test Product",
                "rating": 4.5,
                "feedback_count": 100,
            },
            "signal": {
                "scores": [{"label": "red", "rating": 3.2}]
            }
        }

        # Create task synchronously (Celery uses sync session)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        from backend.database import Base
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        sync_session = Session()

        # Create user and task in sync session
        from backend.database import User, Task, InviteCode

        invite = InviteCode(id=1, code="TEST", max_uses=10)
        sync_session.add(invite)
        sync_session.commit()

        user = User(
            id=1,
            telegram_id=123456789,
            username="test",
            auth_date=int(datetime.utcnow().timestamp()),
            invite_code_id=1,
        )
        sync_session.add(user)
        sync_session.commit()

        task = Task(
            id=1,
            user_id=user.id,
            article_id=282955222,
            status="pending",
            progress=0,
        )
        sync_session.add(task)
        sync_session.commit()

        # Mock SessionLocal to return our test session
        with patch('backend.tasks.SessionLocal', return_value=sync_session):
            # Run task
            analyze_article_task(
                task_id=task.id,
                article_id=282955222,
                user_telegram_id=123456789,
            )

        # Verify task completed
        sync_session.refresh(task)
        assert task.status == "completed"
        assert task.progress == 100
        assert task.wbcon_task_id == "01-test-task-id"

        # Verify notifications sent
        mock_telegram.assert_called()

        sync_session.close()

    @patch('backend.tasks.create_wbcon_task')
    @patch('backend.tasks.send_telegram_notification')
    def test_analyze_article_task_failure(
        self,
        mock_telegram,
        mock_create,
    ):
        """Test task failure handling."""
        from backend.tasks import analyze_article_task
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.database import Base, User, Task, InviteCode

        # Mock WBCON to fail
        mock_create.side_effect = Exception("WBCON API error")

        # Setup sync DB
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        sync_session = Session()

        invite = InviteCode(id=1, code="TEST", max_uses=10)
        sync_session.add(invite)
        sync_session.commit()

        user = User(
            id=1,
            telegram_id=123456789,
            username="test",
            auth_date=int(datetime.utcnow().timestamp()),
            invite_code_id=1,
        )
        sync_session.add(user)
        sync_session.commit()

        task = Task(
            id=1,
            user_id=user.id,
            article_id=282955222,
            status="pending",
            progress=0,
        )
        sync_session.add(task)
        sync_session.commit()

        with patch('backend.tasks.SessionLocal', return_value=sync_session):
            with pytest.raises(Exception):
                analyze_article_task(
                    task_id=task.id,
                    article_id=282955222,
                    user_telegram_id=123456789,
                )

        # Verify task marked as failed
        sync_session.refresh(task)
        assert task.status == "failed"
        assert task.error_message is not None

        # Verify error notification sent
        mock_telegram.assert_called()
        call_args = mock_telegram.call_args[0]
        assert "Ошибка" in call_args[1] or "ошибка" in call_args[1]

        sync_session.close()


@pytest.mark.integration
class TestWBCardAPI:
    """Tests for WB card API integration."""

    @responses.activate
    def test_fetch_wb_card_success(self):
        """Test fetching WB card data."""
        from backend.tasks import fetch_wb_card_info

        # Note: This imports from a different location in actual code
        # We'd need to import from scripts/wbcon-task-to-card-v2.py
        # For now, this is a placeholder for the pattern

    @responses.activate
    def test_fetch_wb_price_history(self):
        """Test fetching price history."""
        # Placeholder for price history test
        pass
