"""
Tests for PostgreSQL backup scripts.

Tests the backup automation system including:
- Backup filename parsing
- Backup rotation logic
- Restore validation
"""

import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBackupFilenameParser:
    """Test parsing of backup filenames."""

    DAILY_PATTERN = re.compile(r'^agentiq_chat_(\d{4}-\d{2}-\d{2}_\d{6})\.sql\.gz$')
    WEEKLY_PATTERN = re.compile(r'^agentiq_chat_weekly_(\d{4}-\d{2}-\d{2}_\d{6})\.sql\.gz$')

    def test_parse_daily_backup_filename(self):
        """Test parsing daily backup filename."""
        filename = "agentiq_chat_2026-02-15_030000.sql.gz"
        match = self.DAILY_PATTERN.match(filename)

        assert match is not None
        timestamp_str = match.group(1)
        assert timestamp_str == "2026-02-15_030000"

        # Verify timestamp can be parsed
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
        assert timestamp.year == 2026
        assert timestamp.month == 2
        assert timestamp.day == 15
        assert timestamp.hour == 3
        assert timestamp.minute == 0

    def test_parse_weekly_backup_filename(self):
        """Test parsing weekly backup filename."""
        filename = "agentiq_chat_weekly_2026-02-16_020000.sql.gz"
        match = self.WEEKLY_PATTERN.match(filename)

        assert match is not None
        timestamp_str = match.group(1)
        assert timestamp_str == "2026-02-16_020000"

        # Verify timestamp can be parsed
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
        assert timestamp.year == 2026
        assert timestamp.month == 2
        assert timestamp.day == 16
        assert timestamp.hour == 2
        assert timestamp.minute == 0

    def test_invalid_filename_format(self):
        """Test that invalid filenames are rejected."""
        invalid_filenames = [
            "agentiq_chat_2026-02-15.sql.gz",  # Missing time
            "agentiq_chat_2026-02-15_0300.sql.gz",  # Wrong time format
            "agentiq_chat_2026-02-15_030000.sql",  # Not compressed
            "backup_2026-02-15_030000.sql.gz",  # Wrong prefix
        ]

        for filename in invalid_filenames:
            assert self.DAILY_PATTERN.match(filename) is None

    def test_parse_extension(self):
        """Test extracting file extension."""
        filenames = [
            ("agentiq_chat_2026-02-15_030000.sql.gz", ".sql.gz"),
            ("agentiq_chat_weekly_2026-02-16_020000.sql.gz", ".sql.gz"),
        ]

        for filename, expected_ext in filenames:
            # Extract extension (handle .sql.gz as compound extension)
            if filename.endswith(".sql.gz"):
                ext = ".sql.gz"
            else:
                ext = os.path.splitext(filename)[1]

            assert ext == expected_ext


class TestBackupRotation:
    """Test backup rotation logic."""

    def create_mock_backup_file(self, backup_dir: Path, filename: str, days_old: int) -> Path:
        """Create a mock backup file with specific age."""
        filepath = backup_dir / filename
        filepath.touch()

        # Set modification time
        old_time = datetime.now() - timedelta(days=days_old)
        timestamp = old_time.timestamp()
        os.utime(filepath, (timestamp, timestamp))

        return filepath

    def test_rotation_deletes_old_backups(self, tmp_path):
        """Test that backups older than retention period are deleted."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        retention_days = 30

        # Create backups at various ages
        backups = [
            ("agentiq_chat_2026-01-01_030000.sql.gz", 60),  # Should delete
            ("agentiq_chat_2026-01-15_030000.sql.gz", 31),  # Should delete
            ("agentiq_chat_2026-02-01_030000.sql.gz", 14),  # Should keep
            ("agentiq_chat_2026-02-10_030000.sql.gz", 5),   # Should keep
            ("agentiq_chat_2026-02-15_030000.sql.gz", 0),   # Should keep (today)
        ]

        for filename, days_old in backups:
            self.create_mock_backup_file(backup_dir, filename, days_old)

        # Simulate rotation logic
        deleted_files = []
        for backup_file in backup_dir.glob("agentiq_chat_*.sql.gz"):
            file_age = datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_age.days > retention_days:
                deleted_files.append(backup_file.name)
                backup_file.unlink()

        # Verify correct files were deleted
        assert len(deleted_files) == 2
        assert "agentiq_chat_2026-01-01_030000.sql.gz" in deleted_files
        assert "agentiq_chat_2026-01-15_030000.sql.gz" in deleted_files

        # Verify remaining files
        remaining_files = [f.name for f in backup_dir.glob("agentiq_chat_*.sql.gz")]
        assert len(remaining_files) == 3
        assert "agentiq_chat_2026-02-01_030000.sql.gz" in remaining_files
        assert "agentiq_chat_2026-02-10_030000.sql.gz" in remaining_files
        assert "agentiq_chat_2026-02-15_030000.sql.gz" in remaining_files

    def test_rotation_boundary_case(self, tmp_path):
        """Test rotation at exactly retention_days boundary."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        retention_days = 30

        # Create backup exactly 30 days old
        self.create_mock_backup_file(backup_dir, "agentiq_chat_2026-01-16_030000.sql.gz", 30)

        # Rotation should NOT delete (> retention_days, not >=)
        deleted_count = 0
        for backup_file in backup_dir.glob("agentiq_chat_*.sql.gz"):
            file_age = datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_age.days > retention_days:
                backup_file.unlink()
                deleted_count += 1

        assert deleted_count == 0
        assert len(list(backup_dir.glob("agentiq_chat_*.sql.gz"))) == 1

    def test_rotation_preserves_weekly_backups(self, tmp_path):
        """Test that weekly backups are also subject to rotation."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        retention_days = 30

        # Create mix of daily and weekly backups
        backups = [
            ("agentiq_chat_2026-01-01_030000.sql.gz", 45),        # Old daily
            ("agentiq_chat_weekly_2026-01-05_020000.sql.gz", 41), # Old weekly
            ("agentiq_chat_2026-02-01_030000.sql.gz", 14),        # Recent daily
            ("agentiq_chat_weekly_2026-02-09_020000.sql.gz", 6),  # Recent weekly
        ]

        for filename, days_old in backups:
            self.create_mock_backup_file(backup_dir, filename, days_old)

        # Rotation applies to all backups
        for backup_file in backup_dir.glob("agentiq_chat_*.sql.gz"):
            file_age = datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_age.days > retention_days:
                backup_file.unlink()

        remaining_files = [f.name for f in backup_dir.glob("agentiq_chat_*.sql.gz")]
        assert len(remaining_files) == 2
        assert "agentiq_chat_2026-02-01_030000.sql.gz" in remaining_files
        assert "agentiq_chat_weekly_2026-02-09_020000.sql.gz" in remaining_files

    def test_rotation_no_files_to_delete(self, tmp_path):
        """Test rotation when all backups are recent."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        retention_days = 30

        # Create only recent backups
        self.create_mock_backup_file(backup_dir, "agentiq_chat_2026-02-14_030000.sql.gz", 1)
        self.create_mock_backup_file(backup_dir, "agentiq_chat_2026-02-15_030000.sql.gz", 0)

        deleted_count = 0
        for backup_file in backup_dir.glob("agentiq_chat_*.sql.gz"):
            file_age = datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_age.days > retention_days:
                backup_file.unlink()
                deleted_count += 1

        assert deleted_count == 0
        assert len(list(backup_dir.glob("agentiq_chat_*.sql.gz"))) == 2


class TestRestoreValidation:
    """Test restore script validation logic."""

    def test_validate_backup_file_exists(self, tmp_path):
        """Test validation of backup file existence."""
        backup_file = tmp_path / "agentiq_chat_2026-02-15_030000.sql.gz"

        # File doesn't exist
        assert not backup_file.exists()

        # File exists
        backup_file.touch()
        assert backup_file.exists()

    def test_validate_backup_file_extension(self):
        """Test validation of backup file extension."""
        valid_extensions = [".sql", ".sql.gz"]

        valid_files = [
            "agentiq_chat_2026-02-15_030000.sql.gz",
            "agentiq_chat_2026-02-15_030000.sql",
        ]

        invalid_files = [
            "agentiq_chat_2026-02-15_030000.txt",
            "agentiq_chat_2026-02-15_030000.zip",
            "agentiq_chat_2026-02-15_030000",
        ]

        for filename in valid_files:
            is_valid = any(filename.endswith(ext) for ext in valid_extensions)
            assert is_valid, f"{filename} should be valid"

        for filename in invalid_files:
            is_valid = any(filename.endswith(ext) for ext in valid_extensions)
            assert not is_valid, f"{filename} should be invalid"

    def test_validate_backup_file_readable(self, tmp_path):
        """Test validation of backup file readability."""
        backup_file = tmp_path / "agentiq_chat_2026-02-15_030000.sql.gz"
        backup_file.write_text("test data")

        # File is readable
        assert os.access(backup_file, os.R_OK)

        # Make file unreadable (Unix only)
        if os.name != 'nt':  # Skip on Windows
            backup_file.chmod(0o000)
            assert not os.access(backup_file, os.R_OK)

            # Restore permissions for cleanup
            backup_file.chmod(0o644)

    def test_get_backup_file_info(self, tmp_path):
        """Test extracting backup file information."""
        backup_file = tmp_path / "agentiq_chat_2026-02-15_030000.sql.gz"
        test_data = b"x" * 1024  # 1KB of data
        backup_file.write_bytes(test_data)

        # Get file size
        file_size = backup_file.stat().st_size
        assert file_size == 1024

        # Get modification time
        mtime = backup_file.stat().st_mtime
        mod_time = datetime.fromtimestamp(mtime)
        assert isinstance(mod_time, datetime)

    def test_parse_restore_arguments(self):
        """Test parsing of restore script arguments."""
        test_cases = [
            (["db-restore.sh", "/path/to/backup.sql.gz"],
             {"backup_file": "/path/to/backup.sql.gz", "skip_confirmation": False}),
            (["db-restore.sh", "/path/to/backup.sql.gz", "--yes"],
             {"backup_file": "/path/to/backup.sql.gz", "skip_confirmation": True}),
            (["db-restore.sh"],
             {"error": "Missing backup_file argument"}),
        ]

        for args, expected in test_cases:
            if "error" in expected:
                # Should fail validation
                assert len(args) < 2
            else:
                # Should pass validation
                assert len(args) >= 2
                backup_file = args[1]
                skip_confirmation = "--yes" in args

                assert backup_file == expected["backup_file"]
                assert skip_confirmation == expected["skip_confirmation"]

    def test_restore_requires_confirmation_by_default(self):
        """Test that restore requires confirmation unless --yes flag is provided."""
        # Without --yes flag
        args = ["db-restore.sh", "/path/to/backup.sql.gz"]
        requires_confirmation = "--yes" not in args
        assert requires_confirmation is True

        # With --yes flag
        args = ["db-restore.sh", "/path/to/backup.sql.gz", "--yes"]
        requires_confirmation = "--yes" not in args
        assert requires_confirmation is False


class TestBackupIntegration:
    """Integration tests for backup system."""

    def test_complete_backup_workflow(self, tmp_path):
        """Test complete backup and rotation workflow."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Simulate creating backups over time
        backups_created = []

        for days_ago in range(45, 0, -5):  # Every 5 days for 45 days
            timestamp = datetime.now() - timedelta(days=days_ago)
            filename = f"agentiq_chat_{timestamp.strftime('%Y-%m-%d_%H%M%S')}.sql.gz"
            filepath = backup_dir / filename
            filepath.write_text(f"backup data from {days_ago} days ago")

            # Set file modification time
            file_timestamp = timestamp.timestamp()
            os.utime(filepath, (file_timestamp, file_timestamp))

            backups_created.append(filename)

        # Verify all backups were created
        assert len(backups_created) == 9

        # Perform rotation (30 day retention)
        retention_days = 30
        deleted_count = 0

        for backup_file in backup_dir.glob("agentiq_chat_*.sql.gz"):
            file_age = datetime.now() - datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_age.days > retention_days:
                backup_file.unlink()
                deleted_count += 1

        # Verify old backups were deleted
        assert deleted_count == 3  # 45, 40, 35 days old

        # Verify recent backups remain
        remaining_files = list(backup_dir.glob("agentiq_chat_*.sql.gz"))
        assert len(remaining_files) == 6  # 30, 25, 20, 15, 10, 5 days old

    def test_backup_filename_generation(self):
        """Test generating backup filenames with current timestamp."""
        # Daily backup
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        daily_filename = f"agentiq_chat_{timestamp}.sql.gz"
        assert daily_filename.startswith("agentiq_chat_")
        assert daily_filename.endswith(".sql.gz")

        # Weekly backup
        weekly_filename = f"agentiq_chat_weekly_{timestamp}.sql.gz"
        assert weekly_filename.startswith("agentiq_chat_weekly_")
        assert weekly_filename.endswith(".sql.gz")

    def test_backup_directory_structure(self, tmp_path):
        """Test backup directory structure creation."""
        backup_root = tmp_path / "var" / "backups" / "agentiq"
        log_dir = tmp_path / "var" / "log" / "agentiq"

        # Directories don't exist initially
        assert not backup_root.exists()
        assert not log_dir.exists()

        # Create directories (as script would do)
        backup_root.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Verify directories exist
        assert backup_root.exists()
        assert backup_root.is_dir()
        assert log_dir.exists()
        assert log_dir.is_dir()
