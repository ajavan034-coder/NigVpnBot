#!/bin/bash

REPO="Smertam/NigSeller_Bpt"
INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"
BRANCH="main"

echo ""
echo "========================================="
echo "       NigVpn Bot Installer"
echo "========================================="
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash setup.sh"
    exit 1
fi

echo "[1/6] Installing system dependencies..."
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq git python3 python3-venv python3-pip > /dev/null 2>&1

echo "[2/6] Downloading bot files..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git checkout $BRANCH -q 2>/dev/null
    git pull -q 2>/dev/null
    echo "Updated existing installation."
else
    git clone -b $BRANCH "https://github.com/${REPO}.git" "$INSTALL_DIR" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Git clone failed, downloading via API..."
        mkdir -p "$INSTALL_DIR"
        cd "$INSTALL_DIR"
        API_URL="https://api.github.com/repos/${REPO}/contents"
        FILES=$(curl -s "$API_URL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data:
    print(item['name'], item['type'])
")
        for LINE in $FILES; do
            NAME=$(echo $LINE | cut -d' ' -f1)
            TYPE=$(echo $LINE | cut -d' ' -f2)
            if [ "$TYPE" = "file" ]; then
                curl -s "$API_URL/$NAME" | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
content = base64.b64decode(data['content']).decode()
with open('$NAME', 'w') as f:
    f.write(content)
"
                echo "Downloaded: $NAME"
            elif [ "$TYPE" = "dir" ]; then
                mkdir -p "$NAME"
                SUB_FILES=$(curl -s "$API_URL/$NAME" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data:
    print(item['name'], item['type'])
")
                for SUB in $SUB_FILES; do
                    SUB_NAME=$(echo $SUB | cut -d' ' -f1)
                    SUB_TYPE=$(echo $SUB | cut -d' ' -f2)
                    if [ "$SUB_TYPE" = "file" ]; then
                        curl -s "$API_URL/$NAME/$SUB_NAME" | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
content = base64.b64decode(data['content']).decode()
with open('$NAME/$SUB_NAME', 'w') as f:
    f.write(content)
"
                        echo "Downloaded: $NAME/$SUB_NAME"
                    fi
                done
            fi
        done
        echo "Downloaded via API."
    else
        cd "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR" 2>/dev/null || { echo "Error: Cannot access $INSTALL_DIR"; exit 1; }

echo "[3/6] Installing Python packages..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q

echo "[4/6] Configuring..."
echo ""

OLD_TOKEN=""
OLD_ADMIN=""
OLD_PORT=""
OLD_WEB_USER=""
OLD_WEB_PASS=""

if [ -f .env ]; then
    OLD_TOKEN=$(grep BOT_TOKEN .env 2>/dev/null | cut -d= -f2)
    OLD_ADMIN=$(grep ADMIN_IDS .env 2>/dev/null | cut -d= -f2)
    OLD_PORT=$(grep WEB_PORT .env 2>/dev/null | cut -d= -f2)
    OLD_WEB_USER=$(grep ADMIN_WEB_USER .env 2>/dev/null | cut -d= -f2)
    OLD_WEB_PASS=$(grep ADMIN_WEB_PASS .env 2>/dev/null | cut -d= -f2)
    echo "Existing .env found. Press Enter to keep current value."
    echo ""
fi

read -p "Bot Token: " BOT_TOKEN
BOT_TOKEN=${BOT_TOKEN:-$OLD_TOKEN}
if [ -z "$BOT_TOKEN" ]; then echo "Error: Bot Token is required!"; exit 1; fi

read -p "Admin Telegram IDs: " ADMIN_IDS
ADMIN_IDS=${ADMIN_IDS:-$OLD_ADMIN}
if [ -z "$ADMIN_IDS" ]; then echo "Error: Admin IDs are required!"; exit 1; fi

read -p "Web Panel Port [$OLD_PORT]: " WEB_PORT
WEB_PORT=${WEB_PORT:-$OLD_PORT:-5000}

read -p "Admin Panel Username [$OLD_WEB_USER]: " ADMIN_WEB_USER
ADMIN_WEB_USER=${ADMIN_WEB_USER:-$OLD_WEB_USER:-admin}

read -p "Admin Panel Password [$OLD_WEB_PASS]: " ADMIN_WEB_PASS
ADMIN_WEB_PASS=${ADMIN_WEB_PASS:-$OLD_WEB_PASS}

SECRET_KEY=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | head -c 32)

OLD_PANEL_URL=""
OLD_PANEL_USER=""
OLD_PANEL_PASS=""
OLD_CHANNEL=""
if [ -f .env ]; then
    OLD_PANEL_URL=$(grep PANEL_URL .env 2>/dev/null | cut -d= -f2-)
    OLD_PANEL_USER=$(grep PANEL_USER .env 2>/dev/null | cut -d= -f2)
    OLD_PANEL_PASS=$(grep PANEL_PASS .env 2>/dev/null | cut -d= -f2)
    OLD_CHANNEL=$(grep CHANNEL_ID .env 2>/dev/null | cut -d= -f2)
fi

cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
CHANNEL_ID=$OLD_CHANNEL

PANEL_URL=$OLD_PANEL_URL
PANEL_USER=$OLD_PANEL_USER
PANEL_PASS=$OLD_PANEL_PASS

CONFIG_PRICE=3000
FREE_TEST_DAYS=1
CONFIG_MONTHS=30

DB_PATH=bot_database.db

ADMIN_WEB_USER=$ADMIN_WEB_USER
ADMIN_WEB_PASS=$ADMIN_WEB_PASS
SECRET_KEY=$SECRET_KEY
WEB_PORT=$WEB_PORT
EOF

echo "[5/6] Setting up service..."
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

OLD_PID=$(lsof -ti:$WEB_PORT 2>/dev/null)
if [ -n "$OLD_PID" ]; then kill -9 $OLD_PID 2>/dev/null; fi

echo "[6/6] Starting bot..."
systemctl restart ${SERVICE_NAME}
sleep 3

echo ""
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "========================================="
    echo "  Bot is running!"
    echo "  Web Panel: http://YOUR_IP:$WEB_PORT"
    echo "  Login: $ADMIN_WEB_USER / $ADMIN_WEB_PASS"
    echo "  Logs: tail -f $INSTALL_DIR/bot.log"
    echo "  Status: systemctl status ${SERVICE_NAME}"
    echo "========================================="
else
    echo "========================================="
    echo "  Error! Check: tail -50 $INSTALL_DIR/bot.log"
    echo "========================================="
fi