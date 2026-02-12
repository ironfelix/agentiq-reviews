#!/usr/bin/env python3
"""Test Wildberries Chat API tokens (NO SECRETS IN REPO).

This script hits real Wildberries endpoints. Tokens MUST be provided via env vars:

- WB_TOKEN_PRODUCTION
- WB_TOKEN_TEST (optional)

Usage:
    WB_TOKEN_PRODUCTION='...' WB_TOKEN_TEST='...' python test_wb_tokens.py

Security:
- Do NOT paste tokens into this file.
- The generated report is intentionally redacted and should not be committed.
"""

import httpx
import json
import base64
import os
from datetime import datetime
from typing import Dict, Any, List


# WB API Configuration
WB_API_BASE = "https://buyer-chat-api.wildberries.ru"

WB_TOKEN_PRODUCTION = os.environ.get("WB_TOKEN_PRODUCTION", "").strip()
WB_TOKEN_TEST = os.environ.get("WB_TOKEN_TEST", "").strip()


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    """Decode JWT payload without verification."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {"error": "Invalid JWT format"}

        # Add padding if needed
        payload = parts[1]
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += '=' * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        return {"error": str(e)}


def test_endpoint(
    client: httpx.Client,
    endpoint: str,
    method: str = "GET",
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Test a single endpoint."""
    url = f"{WB_API_BASE}{endpoint}"

    try:
        if method == "GET":
            response = client.get(url, params=params, timeout=10.0)
        else:
            response = client.post(url, json=params, timeout=10.0)

        result = {
            "endpoint": endpoint,
            "method": method,
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
        }

        # Never store response bodies (can contain buyer names/messages).
        result["content_type"] = response.headers.get("content-type", "unknown")

        return result

    except httpx.TimeoutException:
        return {
            "endpoint": endpoint,
            "method": method,
            "success": False,
            "error": "Request timeout (>10s)",
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "method": method,
            "success": False,
            "error": str(e),
        }


def test_token(token: str, token_name: str) -> Dict[str, Any]:
    """Test single WB token against multiple endpoints."""
    print(f"\n{'='*60}")
    print(f"Testing: {token_name}")
    print(f"{'='*60}")

    # Decode JWT payload
    payload = decode_jwt_payload(token)
    print(f"\nJWT Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    results = {
        "token_name": token_name,
        "timestamp": datetime.now().isoformat(),
        "jwt_payload": payload,
        "tests": []
    }

    # Setup HTTP client with auth header
    headers = {"Authorization": token}

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        def print_test_result(label: str, test_result: Dict[str, Any]) -> None:
            if "status_code" in test_result:
                print(f"Status: {test_result['status_code']}, Success: {test_result['success']}")
                if not test_result["success"]:
                    print(f"Error: {test_result.get('error', test_result.get('response_body'))}")
            else:
                print("Status: N/A, Success: False")
                print(f"Error: {test_result.get('error', 'Unknown error')}")

        # Test 1: GET /api/v1/seller/chats
        print(f"\nTest 1: GET /api/v1/seller/chats")
        test1 = test_endpoint(client, "/api/v1/seller/chats")
        results["tests"].append(test1)
        print_test_result("test1", test1)

        # Test 2: GET /api/v1/seller/events
        print(f"\nTest 2: GET /api/v1/seller/events")
        test2 = test_endpoint(client, "/api/v1/seller/events")
        results["tests"].append(test2)
        print_test_result("test2", test2)

        # Test 3: GET /api/v1/seller/chats with pagination params
        print(f"\nTest 3: GET /api/v1/seller/chats?limit=10&offset=0")
        test3 = test_endpoint(
            client,
            "/api/v1/seller/chats",
            params={"limit": 10, "offset": 0}
        )
        results["tests"].append(test3)
        print_test_result("test3", test3)

    # Summary
    success_count = sum(1 for t in results["tests"] if t["success"])
    total_count = len(results["tests"])
    results["summary"] = {
        "success_count": success_count,
        "total_count": total_count,
        "success_rate": f"{success_count}/{total_count}",
        "all_passed": success_count == total_count
    }

    print(f"\nSummary: {success_count}/{total_count} tests passed")

    return results


def generate_report(prod_results: Dict, test_results: Dict) -> str:
    """Generate markdown report from test results."""
    report = f"""# Wildberries API Tokens Test Report (Redacted)

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This report intentionally does **not** include tokens, JWT payloads, or API response bodies.

## Summary

| Token | Success Rate | All Passed |
|-------|--------------|------------|
| Production | {prod_results['summary']['success_rate']} | {'✅' if prod_results['summary']['all_passed'] else '❌'} |
| Test | {test_results['summary']['success_rate']} | {'✅' if test_results['summary']['all_passed'] else '❌'} |

## Token Details

### Production Token

**Test Results:**

"""

    for i, test in enumerate(prod_results['tests'], 1):
        status = '✅' if test['success'] else '❌'
        report += f"{i}. {status} `{test['method']} {test['endpoint']}`\n"
        report += f"   - Status: `{test['status_code']}`\n"
        if 'response_time_ms' in test:
            report += f"   - Response time: {test['response_time_ms']}ms\n"
        if not test["success"] and test.get("error"):
            report += f"   - Error: `{test['error']}`\n"
        report += "\n"

    report += f"""### Test Token

**Test Results:**

"""

    for i, test in enumerate(test_results['tests'], 1):
        status = '✅' if test['success'] else '❌'
        report += f"{i}. {status} `{test['method']} {test['endpoint']}`\n"
        report += f"   - Status: `{test['status_code']}`\n"
        if 'response_time_ms' in test:
            report += f"   - Response time: {test['response_time_ms']}ms\n"
        if not test["success"] and test.get("error"):
            report += f"   - Error: `{test['error']}`\n"
        report += "\n"

    report += """## Recommendations

"""

    # Determine which token to use
    if prod_results['summary']['all_passed']:
        report += "- ✅ Use **Production token** for integration\n"
    elif test_results['summary']['all_passed']:
        report += "- ⚠️ Use **Test token** for integration (production token failed)\n"
    else:
        report += "- ❌ Both tokens have issues - contact WB API support\n"

    report += f"""
## API Endpoints Tested

1. `GET /api/v1/seller/chats` - Get list of seller chats
2. `GET /api/v1/seller/events` - Get seller events
3. `GET /api/v1/seller/chats?limit=10&offset=0` - Get chats with pagination

## Notes

- Base URL: `{WB_API_BASE}`
- Auth method: `Authorization: <token>` header (no "Bearer" prefix)
- JWT signature algorithm: ES256 (ECDSA with SHA-256)
"""

    return report


def main():
    """Main test runner."""
    print("="*60)
    print("Wildberries API Token Test Suite")
    print("="*60)

    if not WB_TOKEN_PRODUCTION:
        raise SystemExit(
            "WB_TOKEN_PRODUCTION is required. Run like:\n"
            "  WB_TOKEN_PRODUCTION='...' WB_TOKEN_TEST='...' python test_wb_tokens.py"
        )

    prod_results = test_token(WB_TOKEN_PRODUCTION, "Production")
    test_results = (
        test_token(WB_TOKEN_TEST, "Test")
        if WB_TOKEN_TEST
        else {
            "token_name": "Test",
            "timestamp": datetime.now().isoformat(),
            "jwt_payload": {"note": "WB_TOKEN_TEST not provided"},
            "tests": [],
            "summary": {"success_count": 0, "total_count": 0, "success_rate": "0/0", "all_passed": False},
        }
    )

    # Generate report
    print(f"\n{'='*60}")
    print("Generating report...")
    print(f"{'='*60}")

    report = generate_report(prod_results, test_results)

    # Save report
    report_path = "WB_TOKENS_TEST_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ Report saved to: {report_path}")

    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Production: {prod_results['summary']['success_rate']} tests passed")
    print(f"Test: {test_results['summary']['success_rate']} tests passed")

    if prod_results['summary']['all_passed'] or test_results['summary']['all_passed']:
        print("\n✅ At least one token is working!")
    else:
        print("\n❌ Both tokens have issues - check the report for details")


if __name__ == "__main__":
    main()
