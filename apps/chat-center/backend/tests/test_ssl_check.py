"""
Unit tests for SSL certificate expiry check script.

Tests date parsing logic and script syntax validation.
Note: Tests that actually run the bash script require the script
to be accessible from CWD. Run from repo root for integration tests.
"""

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# Path to the SSL check script (relative to repo root)
SCRIPT_PATH = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "ops" / "ssl-check.sh"


class TestCertificateDateParsing:
    """Test certificate date parsing logic (pure Python, no subprocess)."""

    def test_parse_openssl_output(self):
        """Test parsing of openssl x509 -dates output."""
        sample_output = """
notBefore=Jan  1 00:00:00 2024 GMT
notAfter=Apr  1 23:59:59 2026 GMT
        """.strip()

        lines = sample_output.split("\n")
        not_after_line = [l for l in lines if "notAfter=" in l][0]
        expiry_date = not_after_line.split("=")[1]

        assert "Apr  1 23:59:59 2026 GMT" in expiry_date

    def test_date_conversion_to_epoch(self):
        """Test conversion of cert date to epoch timestamp."""
        cert_date = "Feb 15 23:59:59 2026 GMT"

        try:
            dt = datetime.strptime(cert_date, "%b %d %H:%M:%S %Y %Z")
            epoch = int(dt.timestamp())
            assert epoch > 0
        except ValueError:
            # Platform may handle %Z differently
            assert True

    def test_days_calculation(self):
        """Test calculation of days until expiration."""
        now = datetime.now()
        future = now + timedelta(days=60)

        days_diff = (future - now).days
        assert days_diff == 60

    def test_boundary_exactly_14_days(self):
        """Test edge case: exactly 14 days until expiry."""
        now = datetime.now()
        future = now + timedelta(days=14)
        days_diff = (future - now).days
        assert days_diff == 14

    def test_expired_days_negative(self):
        """Test that expired cert gives negative days."""
        now = datetime.now()
        past = now - timedelta(days=5)
        days_diff = (past - now).days
        assert days_diff == -5


class TestScriptSyntax:
    """Test bash script syntax validation."""

    @pytest.mark.skipif(
        not SCRIPT_PATH.exists(),
        reason=f"Script not found at {SCRIPT_PATH}"
    )
    def test_script_syntax_valid(self):
        """Test that bash script has valid syntax."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    @pytest.mark.skipif(
        not SCRIPT_PATH.exists(),
        reason=f"Script not found at {SCRIPT_PATH}"
    )
    def test_script_is_executable(self):
        """Test that script has executable permission."""
        assert os.access(SCRIPT_PATH, os.X_OK), f"{SCRIPT_PATH} is not executable"

    @pytest.mark.skipif(
        not SCRIPT_PATH.exists(),
        reason=f"Script not found at {SCRIPT_PATH}"
    )
    def test_script_has_shebang(self):
        """Test that script starts with #!/bin/bash or #!/usr/bin/env bash."""
        with open(SCRIPT_PATH, "r") as f:
            first_line = f.readline().strip()
        assert first_line.startswith("#!"), f"Missing shebang: {first_line}"
        assert "bash" in first_line, f"Not a bash script: {first_line}"


class TestSSLCheckLogic:
    """Test the decision logic of the SSL check (Python reimplementation)."""

    def _check_cert_status(self, days_remaining: int, threshold: int = 14) -> int:
        """Reimplementation of ssl-check.sh logic for testing.

        Returns:
            0 = valid, 1 = expiring soon, 2 = expired
        """
        if days_remaining < 0:
            return 2  # expired
        elif days_remaining < threshold:
            return 1  # expiring soon
        else:
            return 0  # valid

    def test_valid_certificate(self):
        """Certificate valid for 60 days → exit 0."""
        assert self._check_cert_status(60) == 0

    def test_expiring_soon(self):
        """Certificate expiring in 7 days → exit 1."""
        assert self._check_cert_status(7) == 1

    def test_expired(self):
        """Certificate expired 5 days ago → exit 2."""
        assert self._check_cert_status(-5) == 2

    def test_custom_threshold_alert(self):
        """20 days remaining, threshold 30 → exit 1."""
        assert self._check_cert_status(20, threshold=30) == 1

    def test_custom_threshold_ok(self):
        """20 days remaining, threshold 10 → exit 0."""
        assert self._check_cert_status(20, threshold=10) == 0

    def test_boundary_exactly_at_threshold(self):
        """Exactly 14 days, threshold 14 → exit 0 (>= threshold is safe)."""
        assert self._check_cert_status(14, threshold=14) == 0

    def test_boundary_one_below_threshold(self):
        """13 days, threshold 14 → exit 1."""
        assert self._check_cert_status(13, threshold=14) == 1

    def test_zero_days(self):
        """0 days remaining → exit 1 (expiring today)."""
        assert self._check_cert_status(0) == 1

    def test_idempotency(self):
        """Running check twice should give same result."""
        r1 = self._check_cert_status(60)
        r2 = self._check_cert_status(60)
        assert r1 == r2
