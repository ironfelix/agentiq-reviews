#!/bin/bash
# =============================================================================
# AgentIQ Post-Deploy Smoke Test
# =============================================================================
#
# Usage:
#   ./smoke-test.sh                    # Test agentiq.ru (default)
#   ./smoke-test.sh https://agentiq.ru # Explicit URL
#   ./smoke-test.sh http://localhost:8001  # Test local backend
#
# Exit code:
#   0 = all checks passed
#   1 = one or more failures
#
# Add to deploy script:
#   ./scripts/ops/smoke-test.sh || echo "SMOKE TEST FAILED"
# =============================================================================

set -euo pipefail

BASE_URL="${1:-https://agentiq.ru}"
FAILURES=0
TOTAL=0
START_TIME=$(date +%s)

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_http() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local actual_status

    TOTAL=$((TOTAL + 1))
    actual_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [ "$actual_status" = "$expected_status" ]; then
        echo -e "${GREEN}[PASS]${NC} $name (HTTP $actual_status)"
    else
        echo -e "${RED}[FAIL]${NC} $name (expected $expected_status, got $actual_status)"
        FAILURES=$((FAILURES + 1))
    fi
}

check_body_contains() {
    local name="$1"
    local url="$2"
    local expected_text="$3"
    local body

    TOTAL=$((TOTAL + 1))
    local tmpfile="/tmp/smoke_body_$$"
    curl -s --compressed --max-time 10 "$url" > "$tmpfile" 2>/dev/null || true

    if grep -qi "$expected_text" "$tmpfile" 2>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} $name (body contains '$expected_text')"
    else
        echo -e "${RED}[FAIL]${NC} $name (missing '$expected_text' in response)"
        echo "  Response: $(head -c 200 "$tmpfile")"
        FAILURES=$((FAILURES + 1))
    fi
    rm -f "$tmpfile"
}

check_response_time() {
    local name="$1"
    local url="$2"
    local max_seconds="$3"
    local actual_time

    TOTAL=$((TOTAL + 1))
    actual_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 15 "$url" 2>/dev/null || echo "99")

    # Use awk for float comparison (portable, no bc dependency)
    if awk "BEGIN {exit !($actual_time < $max_seconds)}"; then
        echo -e "${GREEN}[PASS]${NC} $name (${actual_time}s < ${max_seconds}s)"
    else
        echo -e "${RED}[FAIL]${NC} $name (${actual_time}s > ${max_seconds}s limit)"
        FAILURES=$((FAILURES + 1))
    fi
}

check_content_type() {
    local name="$1"
    local url="$2"
    local expected_type="$3"
    local actual_type

    TOTAL=$((TOTAL + 1))
    actual_type=$(curl -s -o /dev/null -w "%{content_type}" --max-time 10 "$url" 2>/dev/null || echo "")

    if echo "$actual_type" | grep -qi "$expected_type"; then
        echo -e "${GREEN}[PASS]${NC} $name (Content-Type: $actual_type)"
    else
        echo -e "${RED}[FAIL]${NC} $name (expected '$expected_type', got '$actual_type')"
        FAILURES=$((FAILURES + 1))
    fi
}

echo "============================================="
echo " AgentIQ Smoke Test"
echo " Base URL: $BASE_URL"
echo " Time:     $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="
echo ""

# ---- Section 1: Endpoints reachable ----
echo -e "${YELLOW}--- Endpoints ---${NC}"

check_http "Landing page" "$BASE_URL/"
check_http "App page (frontend SPA)" "$BASE_URL/app/"
check_http "API health" "$BASE_URL/api/health"

# ---- Section 2: Auth guards ----
echo ""
echo -e "${YELLOW}--- Auth Guards ---${NC}"

check_http "Auth guard: /api/interactions (401)" "$BASE_URL/api/interactions" "401"
check_http "Auth guard: /api/settings/ai (401)" "$BASE_URL/api/settings/ai" "401"
check_http "Auth guard: /api/interactions/chats (401)" "$BASE_URL/api/interactions/chats" "401"

# ---- Section 3: Response body checks ----
echo ""
echo -e "${YELLOW}--- Response Content ---${NC}"

check_body_contains "Health body has status" "$BASE_URL/api/health" '"status"'
check_body_contains "Landing has DOCTYPE" "$BASE_URL/" "DOCTYPE"
check_body_contains "App has root div" "$BASE_URL/app/" 'id="root"'

# ---- Section 4: Content types ----
echo ""
echo -e "${YELLOW}--- Content Types ---${NC}"

check_content_type "API returns JSON" "$BASE_URL/api/health" "application/json"
check_content_type "App returns HTML" "$BASE_URL/app/" "text/html"

# ---- Section 5: Celery health (optional) ----
echo ""
echo -e "${YELLOW}--- Background Services ---${NC}"

celery_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$BASE_URL/api/interactions/health/celery" 2>/dev/null) || true
TOTAL=$((TOTAL + 1))
if [ "$celery_status" = "200" ]; then
    echo -e "${GREEN}[PASS]${NC} Celery health (HTTP $celery_status)"
elif [ "$celery_status" = "503" ]; then
    echo -e "${YELLOW}[WARN]${NC} Celery unhealthy (HTTP 503) -- workers may be down"
    FAILURES=$((FAILURES + 1))
else
    echo -e "${YELLOW}[WARN]${NC} Celery health check unavailable (HTTP $celery_status)"
    # Don't count as failure -- endpoint may not exist in all envs
fi

# ---- Section 6: Performance ----
echo ""
echo -e "${YELLOW}--- Performance ---${NC}"

check_response_time "API health response time" "$BASE_URL/api/health" "2.0"
check_response_time "Landing page load time" "$BASE_URL/" "3.0"
check_response_time "App page load time" "$BASE_URL/app/" "5.0"

# ---- Section 7: SSL (only for https) ----
if [[ "$BASE_URL" == https://* ]]; then
    echo ""
    echo -e "${YELLOW}--- SSL ---${NC}"

    TOTAL=$((TOTAL + 1))
    ssl_expiry=$(echo | openssl s_client -connect "${BASE_URL#https://}:443" -servername "${BASE_URL#https://}" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null || echo "")

    if [ -n "$ssl_expiry" ]; then
        echo -e "${GREEN}[PASS]${NC} SSL certificate valid ($ssl_expiry)"
    else
        echo -e "${RED}[FAIL]${NC} SSL certificate check failed"
        FAILURES=$((FAILURES + 1))
    fi
fi

# ---- Summary ----
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "============================================="
echo " Results: $((TOTAL - FAILURES))/$TOTAL passed"
echo " Duration: ${DURATION}s"

if [ $FAILURES -eq 0 ]; then
    echo -e " Status: ${GREEN}ALL PASSED${NC}"
    echo "============================================="
    exit 0
else
    echo -e " Status: ${RED}$FAILURES FAILURE(S)${NC}"
    echo "============================================="
    exit 1
fi
