#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <article>"
  echo "Requires env vars: WBCON_EMAIL, WBCON_PASS"
  exit 1
fi

: "${WBCON_EMAIL:?WBCON_EMAIL is required}"
: "${WBCON_PASS:?WBCON_PASS is required}"

ARTICLE="$1"

curl -s --get "https://01-img.wbcon.su/get" \
  --data-urlencode "article=${ARTICLE}" \
  --data-urlencode "email=${WBCON_EMAIL}" \
  --data-urlencode "password=${WBCON_PASS}" \
  | python3 -m json.tool
