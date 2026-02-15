#!/usr/bin/env bash
# SSL Certificate Expiry Monitor
# Checks SSL certificate expiration date and alerts if < 14 days
# Usage: ./ssl-check.sh [domain] [alert_threshold_days]

set -euo pipefail

# Configuration
DOMAIN="${1:-agentiq.ru}"
ALERT_THRESHOLD_DAYS="${2:-14}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"  # Optional webhook URL from env

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if openssl is available
if ! command -v openssl &> /dev/null; then
    log_error "openssl is not installed. Please install it first."
    exit 1
fi

# Get certificate expiration date
log_info "Checking SSL certificate for ${DOMAIN}..."

# Use timeout to prevent hanging
CERT_INFO=$(timeout 10 openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" </dev/null 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || true)

if [[ -z "$CERT_INFO" ]]; then
    log_error "Failed to retrieve certificate for ${DOMAIN}"
    exit 1
fi

# Extract expiration date
EXPIRY_DATE=$(echo "$CERT_INFO" | grep "notAfter=" | cut -d= -f2)

if [[ -z "$EXPIRY_DATE" ]]; then
    log_error "Failed to parse expiration date from certificate"
    exit 1
fi

# Convert to epoch timestamp
EXPIRY_EPOCH=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY_DATE" +%s 2>/dev/null || date -d "$EXPIRY_DATE" +%s 2>/dev/null)
CURRENT_EPOCH=$(date +%s)

# Calculate days until expiration
DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))

# Output results
log_info "Certificate expires: ${EXPIRY_DATE}"
log_info "Days until expiry: ${DAYS_UNTIL_EXPIRY}"

# Alert logic
if [[ $DAYS_UNTIL_EXPIRY -lt 0 ]]; then
    log_error "Certificate EXPIRED ${DAYS_UNTIL_EXPIRY#-} days ago!"
    ALERT_MESSAGE="🚨 SSL Certificate EXPIRED for ${DOMAIN} (expired ${DAYS_UNTIL_EXPIRY#-} days ago)"
    EXIT_CODE=2
elif [[ $DAYS_UNTIL_EXPIRY -lt $ALERT_THRESHOLD_DAYS ]]; then
    log_warn "Certificate expires in ${DAYS_UNTIL_EXPIRY} days (threshold: ${ALERT_THRESHOLD_DAYS})"
    ALERT_MESSAGE="⚠️  SSL Certificate expiring soon for ${DOMAIN} (${DAYS_UNTIL_EXPIRY} days left)"
    EXIT_CODE=1
else
    log_info "Certificate is valid (${DAYS_UNTIL_EXPIRY} days remaining)"
    ALERT_MESSAGE=""
    EXIT_CODE=0
fi

# Send webhook alert if configured and alert needed
if [[ -n "$ALERT_MESSAGE" ]]; then
    # Stdout alert (cron will email this)
    echo "======================================"
    echo "$ALERT_MESSAGE"
    echo "Domain: ${DOMAIN}"
    echo "Expires: ${EXPIRY_DATE}"
    echo "Days left: ${DAYS_UNTIL_EXPIRY}"
    echo "======================================"

    # Webhook alert (optional)
    if [[ -n "$ALERT_WEBHOOK" ]]; then
        curl -X POST "$ALERT_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"$ALERT_MESSAGE\",\"domain\":\"$DOMAIN\",\"days_left\":$DAYS_UNTIL_EXPIRY}" \
            --max-time 5 \
            --silent \
            --show-error || log_warn "Failed to send webhook alert"
    fi
fi

exit $EXIT_CODE
