#!/bin/bash

REPO="https://github.com/Smertam/3-xui-telbot.git"
INSTALL_DIR="/root/robot"
BRANCH="master"

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
echo "[1/6] Installing system dependencies..."
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq git python3 python3-venv python3-pip > /dev/null 2>&1

# Setup directory
echo "[2/6] Downloading files..."
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
echo "[3/6] Installing Python packages..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q

# Interactive .env setup
echo "[4/6] Configuring..."
echo ""

OLD_TOKEN=""
OLD_ADMIN=""
OLD_PANEL_URL=""
OLD_PANEL_USER=""
OLD_PANEL_PASS=""

if [ -f .env ]; then
    OLD_TOKEN=$(grep BOT_TOKEN .env 2>/dev/null | cut -d= -f2)
    OLD_ADMIN=$(grep ADMIN_IDS .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_URL=$(grep PANEL_URL .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_USER=$(grep PANEL_USER .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_PASS=$(grep PANEL_PASS .env 2>/dev/null | cut -d= -f2)
    echo "Existing .env found. Press Enter to keep current value."
    echo ""
fi

echo "--- Bot Settings ---"
read -p "Bot Token [$OLD_TOKEN]: " BOT_TOKEN
BOT_TOKEN=${BOT_TOKEN:-$OLD_TOKEN}
read -p "Admin Telegram IDs [$OLD_ADMIN]: " ADMIN_IDS
ADMIN_IDS=${ADMIN_IDS:-$OLD_ADMIN}
read -p "Notification Channel ID (leave empty to skip): " CHANNEL_ID

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
read -p "Config Price (default 5): " CONFIG_PRICE
CONFIG_PRICE=${CONFIG_PRICE:-5}
read -p "Free Test Days (default 1): " FREE_TEST_DAYS
FREE_TEST_DAYS=${FREE_TEST_DAYS:-1}
read -p "Config Duration in Months (default 1): " CONFIG_MONTHS
CONFIG_MONTHS=${CONFIG_MONTHS:-1}

echo ""
echo "--- Web Admin Panel ---"
read -p "Web Panel Username (default admin): " ADMIN_WEB_USER
ADMIN_WEB_USER=${ADMIN_WEB_USER:-admin}
read -p "Web Panel Password (default admin): " ADMIN_WEB_PASS
ADMIN_WEB_PASS=${ADMIN_WEB_PASS:-admin}
read -p "Web Panel Port (default 5000): " WEB_PORT
WEB_PORT=${WEB_PORT:-5000}
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

echo ""
echo "[5/6] Starting robot..."

# Kill old process
OLD_PID=$(lsof -ti:$WEB_PORT 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    kill -9 $OLD_PID 2>/dev/null
fi
sleep 1

# Start bot
nohup ./venv/bin/python run.py > bot.log 2>&1 &
sleep 3

echo "[6/6] Done!"
echo ""
if lsof -ti:$WEB_PORT >/dev/null 2>&1; then
    echo "========================================="
    echo "  Robot is running!"
    echo "  Web Panel: http://YOUR_IP:$WEB_PORT"
    echo "  Login: $ADMIN_WEB_USER / $ADMIN_WEB_PASS"
    echo "  Bot Log: tail -f $INSTALL_DIR/bot.log"
    echo "========================================="
else
    echo "========================================="
    echo "  Something went wrong."
    echo "  Check: tail -50 $INSTALL_DIR/bot.log"
    echo "========================================="
fi
