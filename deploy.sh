#!/bin/bash
set -euo pipefail

INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"

echo "[1/4] Pulling latest code..."
cd "$INSTALL_DIR"

# Backup .env
cp .env .env.bak 2>/dev/null || true

# Pull
if [ -d ".git" ]; then
    git pull origin main -q
else
    echo "Not a git repo. Re-downloading..."
    rm -rf "$INSTALL_DIR"
    git clone -b main https://github.com/ajavan034-coder/NigVpnBot.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Restore .env
cp .env.bak .env 2>/dev/null || true
rm -f .env.bak

echo "[2/4] Updating Python packages..."
$INSTALL_DIR/venv/bin/pip install -q -r requirements.txt

echo "[3/4] Restarting bot..."
systemctl restart "$SERVICE_NAME"

sleep 3
echo "[4/4] Done!"
echo ""
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Bot updated and running!"
    systemctl status "$SERVICE_NAME" --no-pager -l | head -5
else
    echo "Error! Check: tail -50 $INSTALL_DIR/bot.log"
fi