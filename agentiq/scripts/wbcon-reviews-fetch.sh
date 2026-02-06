#!/usr/bin/env bash
set -euo pipefail

# WBCON API v2 (2026) — token-based auth
# Docs: https://19-fb.wbcon.su/docs

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <article>"
  echo "Requires env var: WBCON_TOKEN"
  echo ""
  echo "Example:"
  echo "  export WBCON_TOKEN='eyJhbGciOi...'"
  echo "  $(basename "$0") 282955222"
  exit 1
fi

: "${WBCON_TOKEN:?WBCON_TOKEN is required (see https://19-fb.wbcon.su/docs)}"

ARTICLE="$1"
WBCON_FB_BASE="https://19-fb.wbcon.su"

create_task() {
  curl -s -X POST "${WBCON_FB_BASE}/create_task_fb" \
    -H "Content-Type: application/json" \
    -H "token: ${WBCON_TOKEN}" \
    -d "{\"article\":${ARTICLE}}"
}

check_status() {
  local task_id="$1"
  curl -s "${WBCON_FB_BASE}/task_status?task_id=${task_id}" \
    -H "token: ${WBCON_TOKEN}"
}

get_results() {
  local task_id="$1"
  local offset="${2:-0}"
  curl -s "${WBCON_FB_BASE}/get_results_fb?task_id=${task_id}&offset=${offset}" \
    -H "token: ${WBCON_TOKEN}"
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

echo "task_id=$TASK_ID" >&2

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

  if [[ "$READY" == "true" ]] || echo "$STATUS_JSON" | grep -q '"is_ready":true'; then
    echo "Task ready" >&2
    break
  fi

  sleep 5
  if [[ $i -eq 24 ]]; then
    echo "Task not ready after 2 minutes. Last status:"
    echo "$STATUS_JSON"
    exit 2
  fi
done

# Paginated fetch — collect all feedbacks
python3 - "$TASK_ID" "$WBCON_FB_BASE" "$WBCON_TOKEN" <<'PYEOF'
import json, sys, time, urllib.request, urllib.error

task_id, base, token = sys.argv[1], sys.argv[2], sys.argv[3]
all_fbs = []
seen_ids = set()
offset = 0
total = None

while True:
    url = f"{base}/get_results_fb?task_id={task_id}&offset={offset}"
    req = urllib.request.Request(url)
    req.add_header("token", token)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"Error at offset {offset}: {e}", file=sys.stderr)
        break

    if not data or not isinstance(data, list) or len(data) == 0:
        break

    wrapper = data[0]
    if total is None:
        total = wrapper.get("feedback_count", 0)
        print(f"feedback_count={total}, rating={wrapper.get('rating')}", file=sys.stderr)

    fbs = wrapper.get("feedbacks", [])
    if not fbs:
        break

    new = 0
    for fb in fbs:
        fb_id = fb.get("fb_id")
        if fb_id and fb_id in seen_ids:
            continue
        if fb_id:
            seen_ids.add(fb_id)
        all_fbs.append(fb)
        new += 1

    print(f"  offset={offset}: batch={len(fbs)}, new={new}, total={len(all_fbs)}", file=sys.stderr)

    if len(fbs) < 100:
        break
    if total and offset + 100 >= total:
        break

    offset += 100
    time.sleep(0.5)

# Output merged JSON (same structure as single-batch response)
result = [{"feedback_count": total or len(all_fbs), "rating": wrapper.get("rating", 0) if 'wrapper' in dir() else 0, "feedbacks": all_fbs}]
json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
print(f"\nDone: {len(all_fbs)} unique feedbacks collected", file=sys.stderr)
PYEOF
