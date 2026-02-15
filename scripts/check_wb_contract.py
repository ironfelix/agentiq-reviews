#!/usr/bin/env python3
"""
WB API Contract Validator

Validates that WB API responses match expected schemas.
Detects contract drift that could break ingestion pipelines.

Modes:
  offline  — validates fixture files against schema snapshots (no token needed)
  online   — fetches live WB API response and validates against schema snapshots

Usage:
  python scripts/check_wb_contract.py --mode offline
  python scripts/check_wb_contract.py --mode online --token <WB_API_TOKEN>
  python scripts/check_wb_contract.py --mode both --token <WB_API_TOKEN>

Exit codes:
  0 — all checks passed
  1 — one or more violations detected
  2 — runtime error (network, file not found, etc.)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = (
    PROJECT_ROOT
    / "apps"
    / "chat-center"
    / "backend"
    / "tests"
    / "fixtures"
    / "wb_api"
)

FEEDBACKS_FIXTURE = FIXTURES_DIR / "feedbacks_list.json"
QUESTIONS_FIXTURE = FIXTURES_DIR / "questions_list.json"
FEEDBACKS_SNAPSHOT = FIXTURES_DIR / "feedbacks_schema_snapshot.json"
QUESTIONS_SNAPSHOT = FIXTURES_DIR / "questions_schema_snapshot.json"

# ---------------------------------------------------------------------------
# WB API endpoints (for online mode)
# ---------------------------------------------------------------------------

WB_FEEDBACKS_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
WB_QUESTIONS_URL = "https://feedbacks-api.wildberries.ru/api/v1/questions"

# ---------------------------------------------------------------------------
# Type mapping from snapshot strings to Python types
# ---------------------------------------------------------------------------

TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "str": str,
    "int": int,
    "bool": bool,
    "float": (int, float),
    "null_or_dict": (type(None), dict),
}


def _python_type(type_str: str) -> type | tuple[type, ...]:
    """Convert a snapshot type-string to a Python type (or tuple of types)."""
    return TYPE_MAP.get(type_str, object)


# ---------------------------------------------------------------------------
# Core validation helpers
# ---------------------------------------------------------------------------


def _check_required_fields(
    obj: dict,
    required: list[str],
    context: str,
) -> list[str]:
    """Return violations for missing required fields."""
    violations: list[str] = []
    for field in required:
        if field not in obj:
            violations.append(f"[{context}] missing required field: {field}")
    return violations


def _check_field_types(
    obj: dict,
    type_spec: dict[str, str],
    context: str,
) -> list[str]:
    """Return violations for fields present but with wrong type."""
    violations: list[str] = []
    for field, expected_type_str in type_spec.items():
        if field not in obj:
            continue  # missing-field is caught by required check
        value = obj[field]
        expected = _python_type(expected_type_str)
        if not isinstance(value, expected):
            actual = type(value).__name__
            value_repr = repr(value)[:80]
            violations.append(
                f"[{context}] field '{field}' expected {expected_type_str}, "
                f"got {actual} (value={value_repr})"
            )
    return violations


def _detect_new_fields(
    obj: dict,
    known_fields: set[str],
    context: str,
) -> list[str]:
    """Return warnings for fields that exist in response but are not in snapshot."""
    warnings: list[str] = []
    for field in obj:
        if field not in known_fields:
            warnings.append(
                f"[{context}] unexpected new field: '{field}' "
                f"(value type={type(obj[field]).__name__})"
            )
    return warnings


# ---------------------------------------------------------------------------
# Feedbacks validation
# ---------------------------------------------------------------------------


def validate_feedbacks_response(
    data: dict,
    snapshot: dict | None = None,
) -> list[str]:
    """
    Validate a feedbacks API response against the schema snapshot.

    Returns list of violation/warning strings. Empty list = all good.
    """
    if snapshot is None:
        snapshot = _load_json(FEEDBACKS_SNAPSHOT)

    violations: list[str] = []
    envelope = snapshot["envelope"]
    item_schema = snapshot["feedback_item"]
    pd_schema = item_schema["productDetails"]

    # -- Envelope --
    violations.extend(
        _check_required_fields(data, envelope["required_fields"], "feedbacks.envelope")
    )
    if "data" not in data:
        return violations  # can't go deeper

    violations.extend(
        _check_required_fields(
            data["data"], envelope["data_required_fields"], "feedbacks.data"
        )
    )
    if "feedbacks" not in data["data"]:
        return violations

    feedbacks = data["data"]["feedbacks"]
    if not isinstance(feedbacks, list):
        violations.append(
            f"[feedbacks.data] 'feedbacks' expected array, got {type(feedbacks).__name__}"
        )
        return violations

    if len(feedbacks) == 0:
        # Empty list is valid but we can't check item schema
        return violations

    # -- Check each item --
    all_known_fields = set(item_schema["required_fields"]) | set(
        item_schema.get("optional_fields", [])
    )

    for i, fb in enumerate(feedbacks):
        ctx = f"feedbacks[{i}]"
        violations.extend(
            _check_required_fields(fb, item_schema["required_fields"], ctx)
        )
        violations.extend(
            _check_field_types(fb, item_schema["field_types"], ctx)
        )
        violations.extend(
            _detect_new_fields(fb, all_known_fields | {"productDetails"}, ctx)
        )

        # -- productDetails --
        if "productDetails" in fb and isinstance(fb["productDetails"], dict):
            pd = fb["productDetails"]
            pd_ctx = f"{ctx}.productDetails"
            violations.extend(
                _check_required_fields(pd, pd_schema["required_fields"], pd_ctx)
            )
            violations.extend(
                _check_field_types(pd, pd_schema["field_types"], pd_ctx)
            )
            pd_known = set(pd_schema["required_fields"]) | set(
                pd_schema.get("optional_fields", [])
            )
            violations.extend(_detect_new_fields(pd, pd_known, pd_ctx))

    return violations


# ---------------------------------------------------------------------------
# Questions validation
# ---------------------------------------------------------------------------


def validate_questions_response(
    data: dict,
    snapshot: dict | None = None,
) -> list[str]:
    """
    Validate a questions API response against the schema snapshot.

    Returns list of violation/warning strings. Empty list = all good.
    """
    if snapshot is None:
        snapshot = _load_json(QUESTIONS_SNAPSHOT)

    violations: list[str] = []
    envelope = snapshot["envelope"]
    item_schema = snapshot["question_item"]
    pd_schema = item_schema["productDetails"]
    answer_schema = item_schema["answer_object"]

    # -- Envelope --
    violations.extend(
        _check_required_fields(data, envelope["required_fields"], "questions.envelope")
    )
    if "data" not in data:
        return violations

    violations.extend(
        _check_required_fields(
            data["data"], envelope["data_required_fields"], "questions.data"
        )
    )
    if "questions" not in data["data"]:
        return violations

    questions = data["data"]["questions"]
    if not isinstance(questions, list):
        violations.append(
            f"[questions.data] 'questions' expected array, got {type(questions).__name__}"
        )
        return violations

    if len(questions) == 0:
        return violations

    # -- Check each item --
    all_known_fields = set(item_schema["required_fields"]) | set(
        item_schema.get("optional_fields", [])
    )

    for i, q in enumerate(questions):
        ctx = f"questions[{i}]"
        violations.extend(
            _check_required_fields(q, item_schema["required_fields"], ctx)
        )
        violations.extend(
            _check_field_types(q, item_schema["field_types"], ctx)
        )
        violations.extend(
            _detect_new_fields(q, all_known_fields | {"productDetails"}, ctx)
        )

        # -- productDetails --
        if "productDetails" in q and isinstance(q["productDetails"], dict):
            pd = q["productDetails"]
            pd_ctx = f"{ctx}.productDetails"
            violations.extend(
                _check_required_fields(pd, pd_schema["required_fields"], pd_ctx)
            )
            violations.extend(
                _check_field_types(pd, pd_schema["field_types"], pd_ctx)
            )
            pd_known = set(pd_schema["required_fields"]) | set(
                pd_schema.get("optional_fields", [])
            )
            violations.extend(_detect_new_fields(pd, pd_known, pd_ctx))

        # -- answer object (when not None) --
        if "answer" in q and q["answer"] is not None:
            if isinstance(q["answer"], dict):
                ans = q["answer"]
                ans_ctx = f"{ctx}.answer"
                violations.extend(
                    _check_required_fields(
                        ans, answer_schema["required_fields"], ans_ctx
                    )
                )
                violations.extend(
                    _check_field_types(ans, answer_schema["field_types"], ans_ctx)
                )
                ans_known = set(answer_schema["required_fields"]) | set(
                    answer_schema.get("optional_fields", [])
                )
                violations.extend(_detect_new_fields(ans, ans_known, ans_ctx))
            else:
                violations.append(
                    f"[{ctx}] 'answer' expected dict or null, "
                    f"got {type(q['answer']).__name__}"
                )

    return violations


# ---------------------------------------------------------------------------
# Structural diff: compare response structure with snapshot
# ---------------------------------------------------------------------------


def compare_with_snapshot(
    current: dict,
    snapshot: dict,
    api_name: str,
) -> list[str]:
    """
    Compare the structural shape of a live response against the snapshot.

    Detects:
    - Fields that were in the snapshot but are now missing from the response
    - Fields in the response that are not in the snapshot (potential additions)
    - Type changes for existing fields
    """
    violations: list[str] = []

    # Determine item key and list key based on api_name
    if api_name == "feedbacks":
        list_key = "feedbacks"
        item_schema_key = "feedback_item"
    elif api_name == "questions":
        list_key = "questions"
        item_schema_key = "question_item"
    else:
        violations.append(f"Unknown api_name: {api_name}")
        return violations

    item_schema = snapshot[item_schema_key]

    # Extract items from response
    items = current.get("data", {}).get(list_key, [])
    if not items:
        violations.append(
            f"[{api_name}] response has no items in data.{list_key} "
            f"-- cannot compare structure"
        )
        return violations

    # Build set of fields seen across all items
    seen_fields: set[str] = set()
    for item in items:
        seen_fields.update(item.keys())

    expected_fields = set(item_schema["required_fields"]) | set(
        item_schema.get("optional_fields", [])
    )

    # Fields in snapshot but missing from ALL items
    never_seen = expected_fields - seen_fields
    for field in sorted(never_seen):
        if field in item_schema["required_fields"]:
            violations.append(
                f"[{api_name}] required field '{field}' not seen in any "
                f"response item -- possible contract break"
            )
        # Optional fields missing is not a violation

    # Fields in response but not in snapshot
    new_fields = seen_fields - expected_fields - {"productDetails", "answer"}
    for field in sorted(new_fields):
        violations.append(
            f"[{api_name}] new field '{field}' found in response but "
            f"not in snapshot -- consider updating snapshot"
        )

    return violations


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    """Load a JSON file and return parsed dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Online mode: fetch live WB API data
# ---------------------------------------------------------------------------


def _fetch_live(url: str, token: str) -> dict:
    """Fetch a live response from WB API. Requires httpx."""
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx is required for online mode. Install: pip install httpx")
        sys.exit(2)

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                url,
                headers={"Authorization": token},
                params={"skip": 0, "take": 5, "isAnswered": True, "order": "dateDesc"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"ERROR: WB API returned {e.response.status_code}: {e.response.text[:200]}")
        sys.exit(2)
    except httpx.RequestError as e:
        print(f"ERROR: WB API request failed: {e}")
        sys.exit(2)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _print_results(
    violations: list[str],
    label: str,
) -> bool:
    """Print violations and return True if any exist."""
    if violations:
        print(f"\n  FAIL: {label} ({len(violations)} issues)")
        for v in violations:
            print(f"    - {v}")
        return True
    else:
        print(f"\n  PASS: {label}")
        return False


def run_offline() -> int:
    """Run offline validation against fixture files. Returns exit code."""
    print("=" * 60)
    print("WB API Contract Check -- OFFLINE mode")
    print("=" * 60)

    has_failures = False

    # --- Feedbacks ---
    print("\n--- Feedbacks ---")
    try:
        fb_data = _load_json(FEEDBACKS_FIXTURE)
        fb_snapshot = _load_json(FEEDBACKS_SNAPSHOT)
    except FileNotFoundError as e:
        print(f"  ERROR: fixture/snapshot not found: {e}")
        return 2

    fb_violations = validate_feedbacks_response(fb_data, fb_snapshot)
    fb_struct = compare_with_snapshot(fb_data, fb_snapshot, "feedbacks")
    has_failures |= _print_results(fb_violations, "feedbacks schema validation")
    has_failures |= _print_results(fb_struct, "feedbacks structural diff")

    # --- Questions ---
    print("\n--- Questions ---")
    try:
        q_data = _load_json(QUESTIONS_FIXTURE)
        q_snapshot = _load_json(QUESTIONS_SNAPSHOT)
    except FileNotFoundError as e:
        print(f"  ERROR: fixture/snapshot not found: {e}")
        return 2

    q_violations = validate_questions_response(q_data, q_snapshot)
    q_struct = compare_with_snapshot(q_data, q_snapshot, "questions")
    has_failures |= _print_results(q_violations, "questions schema validation")
    has_failures |= _print_results(q_struct, "questions structural diff")

    # --- Summary ---
    print("\n" + "=" * 60)
    if has_failures:
        print("RESULT: FAIL -- contract violations detected")
        return 1
    else:
        print("RESULT: PASS -- all contract checks passed")
        return 0


def run_online(token: str) -> int:
    """Run online validation against live WB API. Returns exit code."""
    print("=" * 60)
    print("WB API Contract Check -- ONLINE mode")
    print("=" * 60)

    has_failures = False

    # Load snapshots
    try:
        fb_snapshot = _load_json(FEEDBACKS_SNAPSHOT)
        q_snapshot = _load_json(QUESTIONS_SNAPSHOT)
    except FileNotFoundError as e:
        print(f"  ERROR: snapshot not found: {e}")
        return 2

    # --- Feedbacks ---
    print("\n--- Feedbacks (live) ---")
    fb_data = _fetch_live(WB_FEEDBACKS_URL, token)
    fb_violations = validate_feedbacks_response(fb_data, fb_snapshot)
    fb_struct = compare_with_snapshot(fb_data, fb_snapshot, "feedbacks")
    has_failures |= _print_results(fb_violations, "feedbacks live schema")
    has_failures |= _print_results(fb_struct, "feedbacks live structural diff")

    # --- Questions ---
    print("\n--- Questions (live) ---")
    q_data = _fetch_live(WB_QUESTIONS_URL, token)
    q_violations = validate_questions_response(q_data, q_snapshot)
    q_struct = compare_with_snapshot(q_data, q_snapshot, "questions")
    has_failures |= _print_results(q_violations, "questions live schema")
    has_failures |= _print_results(q_struct, "questions live structural diff")

    # --- Summary ---
    print("\n" + "=" * 60)
    if has_failures:
        print("RESULT: FAIL -- live contract violations detected")
        return 1
    else:
        print("RESULT: PASS -- live contract checks passed")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WB API Contract Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["offline", "online", "both"],
        default="offline",
        help="Validation mode (default: offline)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("WB_API_TOKEN", ""),
        help="WB API token (or set WB_API_TOKEN env var)",
    )

    args = parser.parse_args()

    if args.mode in ("online", "both") and not args.token:
        print("ERROR: --token or WB_API_TOKEN env var required for online mode")
        sys.exit(2)

    exit_code = 0

    if args.mode in ("offline", "both"):
        code = run_offline()
        exit_code = max(exit_code, code)

    if args.mode in ("online", "both"):
        code = run_online(args.token)
        exit_code = max(exit_code, code)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
