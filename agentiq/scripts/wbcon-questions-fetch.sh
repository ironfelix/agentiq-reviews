#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <article>"
  echo "Requires env vars: WBCON_EMAIL, WBCON_PASS, WBCON_QS_BASE"
  exit 1
fi

: "${WBCON_EMAIL:?WBCON_EMAIL is required}"
: "${WBCON_PASS:?WBCON_PASS is required}"
: "${WBCON_QS_BASE:?WBCON_QS_BASE is required (API host)}"

ARTICLE="$1"

create_task() {
  curl -s -X POST "${WBCON_QS_BASE}/create_task_qs?email=${WBCON_EMAIL}&password=${WBCON_PASS}" \
    -H "Content-Type: application/json" \
    -d "{\"article\":${ARTICLE}}"
}

check_status() {
  local task_id="$1"
  curl -s "${WBCON_QS_BASE}/task_status?task_id=${task_id}&email=${WBCON_EMAIL}&password=${WBCON_PASS}"
}

get_results() {
  local task_id="$1"
  curl -s "${WBCON_QS_BASE}/get_results_qs?task_id=${task_id}&email=${WBCON_EMAIL}&password=${WBCON_PASS}"
}

TASK_JSON=$(create_task)
TASK_ID=$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys;
try:
  data=json.load(sys.stdin);
  print(data.get("task_id","") or "")
except Exception:
  print("")')

if [[ -z "$TASK_ID" ]]; then
  echo "Failed to create task. Response:"
  echo "$TASK_JSON"
  exit 1
fi

echo "task_id=$TASK_ID"

# Wait for ready
for i in {1..24}; do
  STATUS_JSON=$(check_status "$TASK_ID")
  READY=$(python3 - <<'PY'
import json, sys
try:
  data = json.load(sys.stdin)
  print(str(data.get("is_ready", "")).lower())
except Exception:
  print("false")
PY
<<< "$STATUS_JSON")

  if [[ "$READY" == "true" ]] || echo "$STATUS_JSON" | grep -q '\"is_ready\":true'; then
    break
  fi

  sleep 5
  if [[ $i -eq 24 ]]; then
    echo "Task not ready after 2 minutes. Last status:"
    echo "$STATUS_JSON"
    exit 2
  fi
done

get_results "$TASK_ID" | python3 -m json.tool
