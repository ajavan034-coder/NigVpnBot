#!/bin/bash

REPO="https://github.com/Smertam/3-xui-telbot.git"
INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"
BRANCH="main"

echo ""
echo "========================================="
echo "       Robot Installer"
echo "========================================="
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash setup.sh"
    exit 1
fi

# Install system dependencies
echo "[1/7] Installing system dependencies..."
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq git python3 python3-venv python3-pip > /dev/null 2>&1

# Setup directory
echo "[2/7] Downloading files..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git checkout $BRANCH -q 2>/dev/null
    git pull -q
    echo "Updated existing installation."
elif [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    git init -q
    git remote add origin "$REPO" 2>/dev/null || git remote set-url origin "$REPO"
    git fetch origin $BRANCH -q
    git checkout $BRANCH -q
    echo "Converted to git repository."
else
    git clone -b $BRANCH "$REPO" "$INSTALL_DIR" -q
    cd "$INSTALL_DIR"
fi

# Setup venv
echo "[3/7] Installing Python packages..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q

# Interactive .env setup
echo "[4/7] Configuring..."
echo ""

OLD_TOKEN=""
OLD_ADMIN=""
OLD_CHANNEL=""
OLD_PANEL_URL=""
OLD_PANEL_USER=""
OLD_PANEL_PASS=""
OLD_PRICE=""
OLD_FREE_DAYS=""
OLD_MONTHS=""
OLD_WEB_USER=""
OLD_WEB_PASS=""
OLD_WEB_PORT=""

if [ -f .env ]; then
    OLD_TOKEN=$(grep BOT_TOKEN .env 2>/dev/null | cut -d= -f2)
    OLD_ADMIN=$(grep ADMIN_IDS .env 2>/dev/null | cut -d= -f2)
    OLD_CHANNEL=$(grep CHANNEL_ID .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_URL=$(grep PANEL_URL .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_USER=$(grep PANEL_USER .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_PASS=$(grep PANEL_PASS .env 2>/dev/null | cut -d= -f2)
    OLD_PRICE=$(grep CONFIG_PRICE .env 2>/dev/null | cut -d= -f2)
    OLD_FREE_DAYS=$(grep FREE_TEST_DAYS .env 2>/dev/null | cut -d= -f2)
    OLD_MONTHS=$(grep CONFIG_MONTHS .env 2>/dev/null | cut -d= -f2)
    OLD_WEB_USER=$(grep ADMIN_WEB_USER .env 2>/dev/null | cut -d= -f2)
    OLD_WEB_PASS=$(grep ADMIN_WEB_PASS .env 2>/dev/null | cut -d= -f2)
    OLD_WEB_PORT=$(grep WEB_PORT .env 2>/dev/null | cut -d= -f2)
    echo "Existing .env found. Press Enter to keep current value."
    echo ""
fi

echo "--- Bot Settings ---"
read -p "Bot Token [$OLD_TOKEN]: " BOT_TOKEN
BOT_TOKEN=${BOT_TOKEN:-$OLD_TOKEN}
read -p "Admin Telegram IDs [$OLD_ADMIN]: " ADMIN_IDS
ADMIN_IDS=${ADMIN_IDS:-$OLD_ADMIN}
read -p "Notification Channel ID (leave empty to skip) [$OLD_CHANNEL]: " CHANNEL_ID
CHANNEL_ID=${CHANNEL_ID:-$OLD_CHANNEL}

echo ""
echo "--- Panel Settings ---"
read -p "Panel URL [$OLD_PANEL_URL]: " PANEL_URL
PANEL_URL=${PANEL_URL:-$OLD_PANEL_URL}
read -p "Panel Username [$OLD_PANEL_USER]: " PANEL_USER
PANEL_USER=${PANEL_USER:-$OLD_PANEL_USER}
read -p "Panel Password [$OLD_PANEL_PASS]: " PANEL_PASS
PANEL_PASS=${PANEL_PASS:-$OLD_PANEL_PASS}

echo ""
echo "--- Config Defaults ---"
read -p "Config Price [$OLD_PRICE]: " CONFIG_PRICE
CONFIG_PRICE=${CONFIG_PRICE:-$OLD_PRICE}
read -p "Free Test Days [$OLD_FREE_DAYS]: " FREE_TEST_DAYS
FREE_TEST_DAYS=${FREE_TEST_DAYS:-$OLD_FREE_DAYS}
read -p "Config Duration in Months [$OLD_MONTHS]: " CONFIG_MONTHS
CONFIG_MONTHS=${CONFIG_MONTHS:-$OLD_MONTHS}

echo ""
echo "--- Web Admin Panel ---"
read -p "Web Panel Username [$OLD_WEB_USER]: " ADMIN_WEB_USER
ADMIN_WEB_USER=${ADMIN_WEB_USER:-$OLD_WEB_USER}
read -p "Web Panel Password [$OLD_WEB_PASS]: " ADMIN_WEB_PASS
ADMIN_WEB_PASS=${ADMIN_WEB_PASS:-$OLD_WEB_PASS}
read -p "Web Panel Port [$OLD_WEB_PORT]: " WEB_PORT
WEB_PORT=${WEB_PORT:-$OLD_WEB_PORT}
SECRET_KEY=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | head -c 32)

# Write .env
cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
CHANNEL_ID=$CHANNEL_ID

PANEL_URL=$PANEL_URL
PANEL_USER=$PANEL_USER
PANEL_PASS=$PANEL_PASS

CONFIG_PRICE=$CONFIG_PRICE
FREE_TEST_DAYS=$FREE_TEST_DAYS
CONFIG_MONTHS=$CONFIG_MONTHS

DB_PATH=bot_database.db

ADMIN_WEB_USER=$ADMIN_WEB_USER
ADMIN_WEB_PASS=$ADMIN_WEB_PASS
SECRET_KEY=$SECRET_KEY
WEB_PORT=$WEB_PORT
EOF

# Setup systemd service
echo "[5/7] Setting up systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<SEOF
[Unit]
Description=NigVpn Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python run.py
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/bot.log
StandardError=append:$INSTALL_DIR/bot.log

[Install]
WantedBy=multi-user.target
SEOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME} > /dev/null 2>&1

# Stop old process if running via nohup
OLD_PID=$(lsof -ti:$WEB_PORT 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    kill -9 $OLD_PID 2>/dev/null
fi

echo "[6/7] Starting robot..."
systemctl restart ${SERVICE_NAME}
sleep 3

echo "[7/7] Done!"
echo ""
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "========================================="
    echo "  Robot is running!"
    echo "  Service: ${SERVICE_NAME}"
    echo "  Web Panel: http://YOUR_IP:$WEB_PORT"
    echo "  Login: $ADMIN_WEB_USER / $ADMIN_WEB_PASS"
    echo "  Bot Log: tail -f $INSTALL_DIR/bot.log"
    echo "  Status: systemctl status ${SERVICE_NAME}"
    echo "========================================="
else
    echo "========================================="
    echo "  Something went wrong."
    echo "  Check: tail -50 $INSTALL_DIR/bot.log"
    echo "  Or:    systemctl status ${SERVICE_NAME}"
    echo "========================================="
fi