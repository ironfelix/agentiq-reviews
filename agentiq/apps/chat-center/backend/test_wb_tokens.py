#!/usr/bin/env python3
"""Test Wildberries API tokens.

Tests both production and test WB API tokens against real endpoints:
- GET /api/v1/seller/chats
- GET /api/v1/seller/events

Usage:
    python test_wb_tokens.py
"""

import httpx
import json
import base64
from datetime import datetime
from typing import Dict, Any, List


# WB API Configuration
WB_API_BASE = "https://buyer-chat-api.wildberries.ru"

# Tokens from .env.wb-tokens
WB_TOKEN_PRODUCTION = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzg2Mzk2Mjc5LCJpZCI6IjAxOWM0MWFiLTZkYTYtNzY1ZS04ZmI5LWU2MjQ3YTY5ZmE3ZSIsImlpZCI6NDQ1MTExMjMsIm9pZCI6NDExMjE4OCwicyI6MTYxMjYsInNpZCI6Ijc2NGJiNWViLWI2MTAtNDI3ZC1iMTY3LTkwNDkzNWZkZTg0OCIsInQiOmZhbHNlLCJ1aWQiOjQ0NTExMTIzfQ.8A2Wj154KAQF_74AoYyX85TO6gwt0JpR2s5ZpNjp8CH7XO18pJoOvm4vz_Nse5E-eMBppRwgSCNTBpU_kN9tJw"

WB_TOKEN_TEST = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjIsImVudCI6MSwiZXhwIjoxNzg2Mzk2Mzc2LCJpZCI6IjAxOWM0MWFjLWU3YTAtN2NkZC1hYjJiLWU4MDNjZTA5MjNkNSIsImlpZCI6NDQ1MTExMjMsIm9pZCI6NDExMjE4OCwicyI6MCwic2lkIjoiNzY0YmI1ZWItYjYxMC00MjdkLWIxNjctOTA0OTM1ZmRlODQ4IiwidCI6dHJ1ZSwidWlkIjo0NDUxMTEyM30.XiI1Xo9u7FCh5wMsdqHnbCcpsex8g9YEgQ7M1QOzJQqWxCorkfeD4K5NpHfbRj_-jlLxbUAv47mJZj02SgaSgQ"


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

        # Try to parse JSON response
        try:
            result["response_body"] = response.json()
        except:
            result["response_body"] = response.text[:500]

        # Add headers info
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
        # Test 1: GET /api/v1/seller/chats
        print(f"\nTest 1: GET /api/v1/seller/chats")
        test1 = test_endpoint(client, "/api/v1/seller/chats")
        results["tests"].append(test1)
        print(f"Status: {test1['status_code']}, Success: {test1['success']}")
        if not test1['success']:
            print(f"Error: {test1.get('error', test1.get('response_body'))}")

        # Test 2: GET /api/v1/seller/events
        print(f"\nTest 2: GET /api/v1/seller/events")
        test2 = test_endpoint(client, "/api/v1/seller/events")
        results["tests"].append(test2)
        print(f"Status: {test2['status_code']}, Success: {test2['success']}")
        if not test2['success']:
            print(f"Error: {test2.get('error', test2.get('response_body'))}")

        # Test 3: GET /api/v1/seller/chats with pagination params
        print(f"\nTest 3: GET /api/v1/seller/chats?limit=10&offset=0")
        test3 = test_endpoint(
            client,
            "/api/v1/seller/chats",
            params={"limit": 10, "offset": 0}
        )
        results["tests"].append(test3)
        print(f"Status: {test3['status_code']}, Success: {test3['success']}")
        if not test3['success']:
            print(f"Error: {test3.get('error', test3.get('response_body'))}")

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
    report = f"""# Wildberries API Tokens Test Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

| Token | Success Rate | All Passed |
|-------|--------------|------------|
| Production | {prod_results['summary']['success_rate']} | {'✅' if prod_results['summary']['all_passed'] else '❌'} |
| Test | {test_results['summary']['success_rate']} | {'✅' if test_results['summary']['all_passed'] else '❌'} |

## Token Details

### Production Token

**JWT Payload:**
```json
{json.dumps(prod_results['jwt_payload'], indent=2, ensure_ascii=False)}
```

**Test Results:**

"""

    for i, test in enumerate(prod_results['tests'], 1):
        status = '✅' if test['success'] else '❌'
        report += f"{i}. {status} `{test['method']} {test['endpoint']}`\n"
        report += f"   - Status: `{test['status_code']}`\n"
        if 'response_time_ms' in test:
            report += f"   - Response time: {test['response_time_ms']}ms\n"
        if not test['success']:
            error_msg = test.get('error', test.get('response_body', 'Unknown error'))
            report += f"   - Error: `{error_msg}`\n"
        report += "\n"

    report += f"""### Test Token

**JWT Payload:**
```json
{json.dumps(test_results['jwt_payload'], indent=2, ensure_ascii=False)}
```

**Test Results:**

"""

    for i, test in enumerate(test_results['tests'], 1):
        status = '✅' if test['success'] else '❌'
        report += f"{i}. {status} `{test['method']} {test['endpoint']}`\n"
        report += f"   - Status: `{test['status_code']}`\n"
        if 'response_time_ms' in test:
            report += f"   - Response time: {test['response_time_ms']}ms\n"
        if not test['success']:
            error_msg = test.get('error', test.get('response_body', 'Unknown error'))
            report += f"   - Error: `{error_msg}`\n"
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
- Token expiration: ~August 2026
- Organization ID: 4112188
- User ID: 44511123

## Full Test Results

### Production Token Details
```json
{json.dumps(prod_results, indent=2, ensure_ascii=False, default=str)}
```

### Test Token Details
```json
{json.dumps(test_results, indent=2, ensure_ascii=False, default=str)}
```
"""

    return report


def main():
    """Main test runner."""
    print("="*60)
    print("Wildberries API Token Test Suite")
    print("="*60)

    # Test both tokens
    prod_results = test_token(WB_TOKEN_PRODUCTION, "Production")
    test_results = test_token(WB_TOKEN_TEST, "Test")

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
