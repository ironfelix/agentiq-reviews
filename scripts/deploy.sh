#!/bin/bash
# AgentIQ Deploy Script with Rollback
# Usage: ./scripts/deploy.sh [--skip-checks] [--skip-tests]
set -euo pipefail

SSH_KEY="$HOME/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem"
VPS="ubuntu@79.137.175.164"
SSH="ssh -i $SSH_KEY $VPS"
SCP="scp -i $SSH_KEY"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKEND_DIR="/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend"
FRONTEND_DIR="/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/frontend"

echo "=============================="
echo " AgentIQ Deploy ($TIMESTAMP)"
echo "=============================="

# --- Step 0: Pre-deploy checks ---
if [[ "${1:-}" != "--skip-checks" ]]; then
    echo ""
    echo "--- Pre-deploy checks ---"

    if [[ "${1:-}" != "--skip-tests" ]]; then
        echo "[0a] TypeScript check..."
        cd "$FRONTEND_DIR"
        npx tsc --noEmit || { echo "ABORT: TypeScript errors"; exit 1; }

        echo "[0b] Backend tests..."
        cd "$BACKEND_DIR"
        source venv/bin/activate
        python -m pytest --tb=short -q 2>&1 | tail -3
        echo "  ✓ All checks passed"
    fi
fi

# --- Step 1: Build frontend ---
echo ""
echo "--- Building frontend ---"
cd "$FRONTEND_DIR"
npm run build || { echo "ABORT: Frontend build failed"; exit 1; }
echo "  ✓ Frontend built"

# --- Step 2: Create backend tarball ---
echo ""
echo "--- Packaging backend ---"
cd "$BACKEND_DIR"
tar czf /tmp/agentiq-backend-deploy.tar.gz app/ alembic/ alembic.ini requirements.txt
echo "  ✓ Backend packaged"

# --- Step 3: Backup current prod (for rollback) ---
echo ""
echo "--- Creating backup on VPS ---"
$SSH "sudo tar czf /tmp/agentiq-backup-${TIMESTAMP}.tar.gz -C /opt/agentiq app/ 2>/dev/null && \
      sudo tar czf /tmp/agentiq-frontend-backup-${TIMESTAMP}.tar.gz -C /var/www/agentiq . 2>/dev/null && \
      echo 'Backup created: /tmp/agentiq-backup-${TIMESTAMP}.tar.gz'"
echo "  ✓ Backup created"

# --- Step 4: Deploy backend ---
echo ""
echo "--- Deploying backend ---"
$SCP /tmp/agentiq-backend-deploy.tar.gz $VPS:/tmp/
$SSH "cd /opt/agentiq && sudo tar xzf /tmp/agentiq-backend-deploy.tar.gz --overwrite 2>/dev/null && \
      sudo chown -R root:root /opt/agentiq/app/ /opt/agentiq/alembic/"
echo "  ✓ Backend deployed"

# --- Step 5: Deploy frontend ---
echo ""
echo "--- Deploying frontend ---"
rsync -avz --delete -e "ssh -i $SSH_KEY" "$FRONTEND_DIR/dist/" $VPS:/tmp/agentiq-frontend/ 2>/dev/null
$SSH "sudo rm -rf /var/www/agentiq/assets/* && \
      sudo cp /tmp/agentiq-frontend/index.html /var/www/agentiq/landing.html && \
      sudo cp -r /tmp/agentiq-frontend/app /var/www/agentiq/ && \
      sudo cp -r /tmp/agentiq-frontend/assets /var/www/agentiq/ && \
      sudo cp /tmp/agentiq-frontend/*.svg /var/www/agentiq/ 2>/dev/null; \
      sudo chown -R www-data:www-data /var/www/agentiq/"
echo "  ✓ Frontend deployed"

# --- Step 6: Install deps if needed ---
echo ""
echo "--- Installing dependencies ---"
$SSH "cd /opt/agentiq && sudo venv/bin/pip install -r requirements.txt 2>&1 | tail -3"

# --- Step 7: Restart services ---
echo ""
echo "--- Restarting services ---"
$SSH "sudo systemctl restart agentiq-api && \
      sudo systemctl restart agentiq-celery && \
      sudo systemctl restart agentiq-celery-beat && \
      sleep 3 && \
      echo 'agentiq-api:' \$(sudo systemctl is-active agentiq-api) && \
      echo 'agentiq-celery:' \$(sudo systemctl is-active agentiq-celery) && \
      echo 'agentiq-celery-beat:' \$(sudo systemctl is-active agentiq-celery-beat)"
echo "  ✓ Services restarted"

# --- Step 8: Smoke test ---
echo ""
echo "--- Smoke test ---"
SMOKE_SCRIPT="$BACKEND_DIR/scripts/ops/smoke-test.sh"
if [ -f "$SMOKE_SCRIPT" ]; then
    if $SMOKE_SCRIPT https://agentiq.ru; then
        echo ""
        echo "=============================="
        echo " DEPLOY SUCCESSFUL ($TIMESTAMP)"
        echo "=============================="
    else
        echo ""
        echo "!!! SMOKE TEST FAILED — ROLLING BACK !!!"
        echo ""
        # Rollback
        $SSH "cd /opt/agentiq && sudo tar xzf /tmp/agentiq-backup-${TIMESTAMP}.tar.gz --overwrite 2>/dev/null && \
              cd /var/www/agentiq && sudo tar xzf /tmp/agentiq-frontend-backup-${TIMESTAMP}.tar.gz --overwrite 2>/dev/null && \
              sudo systemctl restart agentiq-api && \
              sudo systemctl restart agentiq-celery && \
              sudo systemctl restart agentiq-celery-beat"
        echo "  ✓ Rolled back to pre-deploy state"
        echo ""
        echo "=============================="
        echo " DEPLOY FAILED — ROLLED BACK"
        echo "=============================="
        exit 1
    fi
else
    echo "  (smoke test script not found, skipping)"
    echo ""
    echo "=============================="
    echo " DEPLOY COMPLETE ($TIMESTAMP)"
    echo "=============================="
fi
