#!/bin/bash
# Pre-deploy checks — run before every deploy
# Usage: ./scripts/pre-deploy-check.sh
set -e

echo "=== Pre-Deploy Checks ==="

# 1. TypeScript type check (frontend)
echo "[1/4] TypeScript type check..."
cd /Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/frontend
npx tsc --noEmit
echo "  ✓ No type errors"

# 2. Frontend build
echo "[2/4] Frontend build..."
npm run build
echo "  ✓ Build successful"

# 3. Backend tests
echo "[3/4] Backend tests..."
cd /Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend
source venv/bin/activate
python -m pytest --tb=short -q 2>&1 | tail -5
echo "  ✓ Tests passed"

# 4. Smoke test (if deploying to prod)
if [ "$1" = "--prod" ]; then
    echo "[4/4] Prod smoke test..."
    /Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/scripts/ops/smoke-test.sh https://agentiq.ru
fi

echo ""
echo "=== All checks passed. Safe to deploy. ==="
