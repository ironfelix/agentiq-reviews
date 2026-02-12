#!/bin/bash
# AgentIQ Chat Center — deploy script
# VPS: 79.137.175.164
#
# Использование:
#   ./deploy.sh          — полный деплой (build + copy + nginx)
#   ./deploy.sh quick    — только copy (без rebuild)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="/var/www/agentiq"
NGINX_CONF="agentiq"

echo "=== AgentIQ Deploy (VPS 79.137.175.164) ==="

# 1. Build frontend (skip with "quick")
if [ "$1" != "quick" ]; then
    echo "[1/5] Building frontend..."
    cd "$SCRIPT_DIR/frontend"
    npm run build
    echo "  Done: frontend built"
else
    echo "[1/5] Skipping build (quick mode)"
fi

# 2. Create deploy directory
echo "[2/5] Preparing deploy directory..."
sudo mkdir -p "$DEPLOY_DIR/app"
sudo mkdir -p "$DEPLOY_DIR/assets"

# 3. Copy landing
echo "[3/5] Copying landing page..."
sudo cp "$SCRIPT_DIR/../../docs/prototypes/landing.html" "$DEPLOY_DIR/landing.html"
echo "  Done: $DEPLOY_DIR/landing.html"

# 4. Copy built frontend
echo "[4/5] Copying frontend build..."
# Vite produces multi-page dist:
# - dist/app/index.html   (SPA entry for /app/)
# - dist/assets/*         (shared assets referenced as /assets/*)
sudo cp "$SCRIPT_DIR/frontend/dist/app/index.html" "$DEPLOY_DIR/app/index.html"
sudo rm -rf "$DEPLOY_DIR/assets"/*
sudo cp -r "$SCRIPT_DIR/frontend/dist/assets/"* "$DEPLOY_DIR/assets/"
echo "  Done: $DEPLOY_DIR/app/index.html"
echo "  Done: $DEPLOY_DIR/assets/"

# 5. Setup nginx (if not yet)
echo "[5/5] Checking nginx..."
if [ ! -f "/etc/nginx/sites-available/$NGINX_CONF" ]; then
    sudo cp "$SCRIPT_DIR/nginx.conf" "/etc/nginx/sites-available/$NGINX_CONF"
    sudo ln -sf "/etc/nginx/sites-available/$NGINX_CONF" "/etc/nginx/sites-enabled/"
    echo "  Done: nginx config installed"
else
    echo "  Skip: nginx config already exists"
fi

# Set permissions
sudo chown -R www-data:www-data "$DEPLOY_DIR"

# Reload nginx
sudo nginx -t && sudo systemctl reload nginx
echo "  Done: nginx reloaded"

echo ""
echo "=== Deploy complete ==="
echo ""
echo "  Landing:  http://79.137.175.164/"
echo "  App:      http://79.137.175.164/app/"
echo "  API:      http://79.137.175.164/api/"
echo ""
echo "Для привязки домена agentiq.ru:"
echo "  1. DNS A-запись: agentiq.ru -> 79.137.175.164"
echo "  2. В nginx.conf: server_name agentiq.ru www.agentiq.ru;"
echo "  3. sudo certbot --nginx -d agentiq.ru -d www.agentiq.ru"
