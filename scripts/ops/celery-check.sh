#!/bin/bash
#
# Celery health check script for cron monitoring.
#
# Usage:
#   ./celery-check.sh [API_URL] [EMAIL]
#
# Examples:
#   ./celery-check.sh http://localhost:8001/api/interactions/health/celery admin@example.com
#   ./celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru
#
# Cron setup (check every 5 minutes):
#   */5 * * * * /opt/agentiq/scripts/ops/celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru >> /var/log/agentiq-celery-check.log 2>&1
#

set -euo pipefail

# Configuration
API_URL="${1:-http://localhost:8001/api/interactions/health/celery}"
EMAIL="${2:-}"
TIMEOUT=30

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Timestamp
NOW=$(date '+%Y-%m-%d %H:%M:%S')

# Fetch health status
echo "[$NOW] Checking Celery health: $API_URL"

HTTP_CODE=$(curl -s -o /tmp/celery-health.json -w "%{http_code}" --max-time "$TIMEOUT" "$API_URL" 2>/dev/null) || true

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}[ERROR]${NC} HTTP $HTTP_CODE - Failed to fetch Celery health"

    if [ -n "$EMAIL" ]; then
        echo "Subject: [AgentIQ Alert] Celery Health Check Failed" | \
        sendmail -v "$EMAIL" <<EOF
From: noreply@agentiq.ru
To: $EMAIL
Subject: [AgentIQ Alert] Celery Health Check Failed

Timestamp: $NOW
API URL: $API_URL
HTTP Code: $HTTP_CODE

Celery health endpoint is not responding.
Please check:
1. Backend service (systemctl status agentiq-chat)
2. Network connectivity
3. API endpoint availability

--
AgentIQ Ops Monitoring
EOF
    fi

    exit 1
fi

# Parse JSON response
STATUS=$(jq -r '.status // "unknown"' /tmp/celery-health.json)
WORKER_ALIVE=$(jq -r '.worker_alive // false' /tmp/celery-health.json)
QUEUE_LENGTH=$(jq -r '.queue_length // null' /tmp/celery-health.json)
ACTIVE_TASKS=$(jq -r '.active_tasks // null' /tmp/celery-health.json)

echo "Status: $STATUS"
echo "Worker Alive: $WORKER_ALIVE"
echo "Queue Length: $QUEUE_LENGTH"
echo "Active Tasks: $ACTIVE_TASKS"

# Check status and alert if not healthy
if [ "$STATUS" = "down" ]; then
    echo -e "${RED}[CRITICAL]${NC} Celery worker is DOWN"

    if [ -n "$EMAIL" ]; then
        echo "Subject: [AgentIQ CRITICAL] Celery Worker DOWN" | \
        sendmail -v "$EMAIL" <<EOF
From: noreply@agentiq.ru
To: $EMAIL
Subject: [AgentIQ CRITICAL] Celery Worker DOWN

Timestamp: $NOW
Status: $STATUS
Worker Alive: $WORKER_ALIVE

Celery worker is not responding. Background tasks are not being processed.

Impact:
- Chat sync disabled
- AI analysis disabled
- SLA escalation disabled
- Auto-close tasks disabled

Action Required:
1. Check worker service: systemctl status agentiq-celery
2. Check logs: journalctl -u agentiq-celery -n 100
3. Restart if needed: systemctl restart agentiq-celery
4. Check Redis: systemctl status redis

--
AgentIQ Ops Monitoring
EOF
    fi

    exit 2

elif [ "$STATUS" = "degraded" ]; then
    echo -e "${YELLOW}[WARNING]${NC} Celery queue is high: $QUEUE_LENGTH tasks"

    if [ -n "$EMAIL" ]; then
        echo "Subject: [AgentIQ Warning] Celery Queue High" | \
        sendmail -v "$EMAIL" <<EOF
From: noreply@agentiq.ru
To: $EMAIL
Subject: [AgentIQ Warning] Celery Queue High

Timestamp: $NOW
Status: $STATUS
Queue Length: $QUEUE_LENGTH
Active Tasks: $ACTIVE_TASKS

Celery queue is growing (threshold: 100 tasks). Tasks may be delayed.

Possible causes:
- High load (many sellers syncing)
- Slow external API (WB/Ozon rate limiting)
- Worker capacity insufficient

Action:
1. Monitor queue trend
2. Consider scaling workers if sustained
3. Check slow tasks: flower (if enabled)

--
AgentIQ Ops Monitoring
EOF
    fi

    exit 3

elif [ "$STATUS" = "healthy" ]; then
    echo -e "${GREEN}[OK]${NC} Celery is healthy"
    exit 0

else
    echo -e "${YELLOW}[WARNING]${NC} Unknown status: $STATUS"
    exit 4
fi
