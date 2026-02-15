#!/usr/bin/env bash

#
# AgentIQ Automated Load Test Runner
#
# Runs Locust in headless mode with configurable parameters and validates
# performance against target SLAs.
#
# Usage:
#   ./run-load-test.sh                    # Default: 100 users, 5 minutes
#   ./run-load-test.sh --users=50         # Custom user count
#   ./run-load-test.sh --duration=3m      # Custom duration
#   ./run-load-test.sh --host=https://agentiq.ru/api  # Test staging
#
# Environment variables:
#   LOAD_TEST_EMAIL       - Test user email (required)
#   LOAD_TEST_PASSWORD    - Test user password (required)
#   LOAD_TEST_HOST        - API host (default: http://localhost:8001)
#

set -e  # Exit on error

# ========== Configuration ==========

# Default parameters
USERS=100
SPAWN_RATE=10
DURATION="5m"
HOST="${LOAD_TEST_HOST:-http://localhost:8001}"

# Performance thresholds
P95_THRESHOLD_MS=1000
ERROR_RATE_THRESHOLD=0.05  # 5%

# ========== Parse Arguments ==========

for arg in "$@"; do
  case $arg in
    --users=*)
      USERS="${arg#*=}"
      shift
      ;;
    --spawn-rate=*)
      SPAWN_RATE="${arg#*=}"
      shift
      ;;
    --duration=*)
      DURATION="${arg#*=}"
      shift
      ;;
    --host=*)
      HOST="${arg#*=}"
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --users=N           Number of concurrent users (default: 100)"
      echo "  --spawn-rate=N      Users to spawn per second (default: 10)"
      echo "  --duration=TIME     Test duration, e.g. 5m, 30s (default: 5m)"
      echo "  --host=URL          API host URL (default: http://localhost:8001)"
      echo "  --help              Show this help message"
      echo ""
      echo "Environment variables:"
      echo "  LOAD_TEST_EMAIL       Test user email (required)"
      echo "  LOAD_TEST_PASSWORD    Test user password (required)"
      echo ""
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# ========== Pre-flight Checks ==========

echo "============================================================"
echo "AgentIQ Load Test Runner"
echo "============================================================"

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo "❌ Error: locust is not installed"
    echo "Install with: pip install locust"
    exit 1
fi

# Check credentials
if [[ -z "$LOAD_TEST_EMAIL" ]] || [[ -z "$LOAD_TEST_PASSWORD" ]]; then
    echo "❌ Error: LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD must be set"
    echo ""
    echo "Set them with:"
    echo "  export LOAD_TEST_EMAIL='your-email@example.com'"
    echo "  export LOAD_TEST_PASSWORD='your-password'"
    exit 1
fi

# Check if backend is reachable
echo "Checking backend health..."
if ! curl -s -o /dev/null -w "%{http_code}" "$HOST/health" | grep -q "200"; then
    echo "⚠️  Warning: Backend at $HOST may not be reachable"
    echo "Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ========== Run Load Test ==========

echo ""
echo "Test Configuration:"
echo "  Host:        $HOST"
echo "  Users:       $USERS"
echo "  Spawn rate:  $SPAWN_RATE/sec"
echo "  Duration:    $DURATION"
echo "  Thresholds:  p95 < ${P95_THRESHOLD_MS}ms, error rate < $(echo "$ERROR_RATE_THRESHOLD * 100" | bc)%"
echo "============================================================"
echo ""

# Get script directory (to find locustfile.py)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Run locust in headless mode
echo "Starting load test..."
locust -f "$SCRIPT_DIR/locustfile.py" \
    --host="$HOST" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$DURATION" \
    --headless \
    --html="$SCRIPT_DIR/load-test-report.html" \
    --csv="$SCRIPT_DIR/load-test-results" \
    --loglevel=INFO

# ========== Parse Results ==========

echo ""
echo "============================================================"
echo "Analyzing Results..."
echo "============================================================"

# Check if CSV results exist
if [[ ! -f "$SCRIPT_DIR/load-test-results_stats.csv" ]]; then
    echo "❌ Error: Results file not found"
    exit 1
fi

# Extract p95 and error rate from CSV
# Format: "Type","Name","Request Count","Failure Count","Median Response Time","Average Response Time","Min Response Time","Max Response Time","Average Content Size","Requests/s","Failures/s","50%","66%","75%","80%","90%","95%","98%","99%","99.9%","99.99%","100%"

# Get aggregated stats (last line is "Aggregated")
STATS_LINE=$(tail -n 1 "$SCRIPT_DIR/load-test-results_stats.csv")

# Parse CSV fields (handle potential commas in quoted strings)
REQUEST_COUNT=$(echo "$STATS_LINE" | cut -d',' -f3 | tr -d '"')
FAILURE_COUNT=$(echo "$STATS_LINE" | cut -d',' -f4 | tr -d '"')
P95=$(echo "$STATS_LINE" | cut -d',' -f16 | tr -d '"')

# Calculate error rate
if [[ "$REQUEST_COUNT" -gt 0 ]]; then
    ERROR_RATE=$(echo "scale=4; $FAILURE_COUNT / $REQUEST_COUNT" | bc)
else
    ERROR_RATE=0
fi

echo ""
echo "Key Metrics:"
echo "  Total Requests:    $REQUEST_COUNT"
echo "  Total Failures:    $FAILURE_COUNT"
echo "  Error Rate:        $(echo "$ERROR_RATE * 100" | bc)%"
echo "  p95 Latency:       ${P95}ms"
echo ""

# ========== Validate Thresholds ==========

EXIT_CODE=0

echo "Performance Validation:"

# Check p95 latency
if (( $(echo "$P95 < $P95_THRESHOLD_MS" | bc -l) )); then
    echo "  ✅ p95 latency (${P95}ms) < ${P95_THRESHOLD_MS}ms - PASS"
else
    echo "  ❌ p95 latency (${P95}ms) >= ${P95_THRESHOLD_MS}ms - FAIL"
    EXIT_CODE=1
fi

# Check error rate
if (( $(echo "$ERROR_RATE < $ERROR_RATE_THRESHOLD" | bc -l) )); then
    echo "  ✅ Error rate ($(echo "$ERROR_RATE * 100" | bc)%) < $(echo "$ERROR_RATE_THRESHOLD * 100" | bc)% - PASS"
else
    echo "  ❌ Error rate ($(echo "$ERROR_RATE * 100" | bc)%) >= $(echo "$ERROR_RATE_THRESHOLD * 100" | bc)% - FAIL"
    EXIT_CODE=1
fi

# ========== Final Report ==========

echo ""
echo "============================================================"

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✅ LOAD TEST PASSED"
else
    echo "❌ LOAD TEST FAILED"
fi

echo "============================================================"
echo ""
echo "Reports generated:"
echo "  HTML:  $SCRIPT_DIR/load-test-report.html"
echo "  CSV:   $SCRIPT_DIR/load-test-results_stats.csv"
echo ""

exit $EXIT_CODE
