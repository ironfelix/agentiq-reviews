"""Unit tests for database models."""
import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.database import User, Task, Report, Notification, InviteCode


@pytest.mark.unit
class TestUserModel:
    """Tests for User model."""

    async def test_create_user(self, test_db_session):
        """Test creating a user."""
        user = User(
            telegram_id=999888777,
            username="test_create",
            first_name="Create",
            last_name="Test",
            auth_date=int(datetime.utcnow().timestamp()),
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        assert user.id is not None
        assert user.telegram_id == 999888777
        assert user.username == "test_create"
        assert user.created_at is not None

    async def test_telegram_id_unique_constraint(self, test_db_session, test_user):
        """Test telegram_id unique constraint."""
        duplicate_user = User(
            telegram_id=test_user.telegram_id,
            username="duplicate",
            first_name="Dup",
            auth_date=int(datetime.utcnow().timestamp()),
        )
        test_db_session.add(duplicate_user)

        with pytest.raises(IntegrityError):
            await test_db_session.commit()

    async def test_user_relationships(self, test_db_session, test_user, test_task):
        """Test user relationships with tasks."""
        await test_db_session.refresh(test_user, ["tasks"])
        assert len(test_user.tasks) == 1
        assert test_user.tasks[0].id == test_task.id


@pytest.mark.unit
class TestTaskModel:
    """Tests for Task model."""

    async def test_create_task(self, test_db_session, test_user):
        """Test creating a task."""
        task = Task(
            user_id=test_user.id,
            article_id=123456789,
            status="pending",
            progress=0,
        )
        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        assert task.id is not None
        assert task.article_id == 123456789
        assert task.status == "pending"
        assert task.progress == 0
        assert task.created_at is not None
        assert task.completed_at is None

    async def test_task_status_values(self, test_db_session, test_user):
        """Test different task status values."""
        statuses = ["pending", "processing", "completed", "failed"]
        tasks = []

        for status in statuses:
            task = Task(
                user_id=test_user.id,
                article_id=100000 + len(tasks),
                status=status,
                progress=0,
            )
            test_db_session.add(task)
            tasks.append(task)

        await test_db_session.commit()

        for i, status in enumerate(statuses):
            await test_db_session.refresh(tasks[i])
            assert tasks[i].status == status

    async def test_task_progress_range(self, test_db_session, test_user):
        """Test task progress values."""
        for progress in [0, 25, 50, 75, 100]:
            task = Task(
                user_id=test_user.id,
                article_id=200000 + progress,
                status="processing",
                progress=progress,
            )
            test_db_session.add(task)

        await test_db_session.commit()

        result = await test_db_session.execute(
            select(Task).where(Task.user_id == test_user.id)
        )
        all_tasks = result.scalars().all()
        assert len(all_tasks) >= 5

    async def test_task_completed_at(self, test_db_session, test_user):
        """Test completed_at timestamp."""
        task = Task(
            user_id=test_user.id,
            article_id=300000,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
        )
        test_db_session.add(task)
        await test_db_session.commit()
        await test_db_session.refresh(task)

        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)


@pytest.mark.unit
class TestReportModel:
    """Tests for Report model."""

    async def test_create_report(self, test_db_session, test_task):
        """Test creating a report."""
        report_data = {
            "header": {"product_name": "Test", "rating": 4.5},
            "signal": {},
        }

        report = Report(
            task_id=test_task.id,
            article_id=test_task.article_id,
            category="test",
            rating=4.5,
            feedback_count=100,
            target_variant="red",
            data='{"header": {}}',
        )
        test_db_session.add(report)
        await test_db_session.commit()
        await test_db_session.refresh(report)

        assert report.id is not None
        assert report.task_id == test_task.id
        assert report.rating == 4.5

    async def test_report_task_unique_constraint(self, test_db_session, completed_task):
        """Test task_id unique constraint."""
        # Get existing report
        result = await test_db_session.execute(
            select(Report).where(Report.task_id == completed_task.id)
        )
        existing_report = result.scalar_one()
        assert existing_report is not None

        # Try to create duplicate
        duplicate_report = Report(
            task_id=completed_task.id,
            article_id=999999,
            data='{"test": "data"}',
        )
        test_db_session.add(duplicate_report)

        with pytest.raises(IntegrityError):
            await test_db_session.commit()

    async def test_report_share_token(self, test_db_session, test_task):
        """Test share token generation."""
        import secrets

        report = Report(
            task_id=test_task.id,
            article_id=test_task.article_id,
            data='{"test": "data"}',
            share_token=secrets.token_urlsafe(32),
        )
        test_db_session.add(report)
        await test_db_session.commit()
        await test_db_session.refresh(report)

        assert report.share_token is not None
        assert len(report.share_token) > 20


@pytest.mark.unit
class TestInviteCodeModel:
    """Tests for InviteCode model."""

    async def test_create_invite_code(self, test_db_session):
        """Test creating an invite code."""
        invite = InviteCode(
            code="TEST-CODE-123",
            max_uses=10,
            used_count=0,
            created_by="test",
        )
        test_db_session.add(invite)
        await test_db_session.commit()
        await test_db_session.refresh(invite)

        assert invite.id is not None
        assert invite.code == "TEST-CODE-123"
        assert invite.max_uses == 10
        assert invite.used_count == 0

    async def test_invite_code_unique_constraint(self, test_db_session):
        """Test code unique constraint."""
        invite1 = InviteCode(code="DUPLICATE-CODE", max_uses=10)
        test_db_session.add(invite1)
        await test_db_session.commit()

        invite2 = InviteCode(code="DUPLICATE-CODE", max_uses=10)
        test_db_session.add(invite2)

        with pytest.raises(IntegrityError):
            await test_db_session.commit()

    async def test_invite_code_usage(self, test_db_session):
        """Test invite code usage tracking."""
        invite = InviteCode(
            code="USAGE-TEST",
            max_uses=5,
            used_count=0,
        )
        test_db_session.add(invite)
        await test_db_session.commit()
        await test_db_session.refresh(invite)

        # Simulate usage
        invite.used_count += 1
        await test_db_session.commit()
        await test_db_session.refresh(invite)

        assert invite.used_count == 1
        assert invite.used_count < invite.max_uses


@pytest.mark.unit
class TestNotificationModel:
    """Tests for Notification model."""

    async def test_create_notification(self, test_db_session, test_user, test_task):
        """Test creating a notification."""
        notification = Notification(
            user_id=test_user.id,
            task_id=test_task.id,
            message="Test notification message",
        )
        test_db_session.add(notification)
        await test_db_session.commit()
        await test_db_session.refresh(notification)

        assert notification.id is not None
        assert notification.message == "Test notification message"
        assert notification.sent_at is not None

    async def test_notification_relationships(self, test_db_session, test_user, test_task):
        """Test notification relationships."""
        notification = Notification(
            user_id=test_user.id,
            task_id=test_task.id,
            message="Relationship test",
        )
        test_db_session.add(notification)
        await test_db_session.commit()
        await test_db_session.refresh(notification, ["user", "task"])

        assert notification.user.id == test_user.id
        assert notification.task.id == test_task.id
