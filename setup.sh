#!/bin/bash

REPO="ajavan034-coder/NigVpnBot"
INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"
BRANCH="main"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║        NigVpn Bot Installer              ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "  ${RED}✘ Please run as root: sudo bash setup.sh${NC}"
    exit 1
fi

# ── Step 1: System Dependencies ─────────────────────────────
echo -e "${BOLD}${BLUE}[1/7]${NC} Installing system dependencies..."
apt-get update -qq > /dev/null 2>&1
if ! apt-get install -y -qq git curl python3 python3-venv python3-pip lsof > /dev/null 2>&1; then
    echo -e "  ${RED}✘ apt-get install failed — run 'apt-get update' and try again${NC}"
    exit 1
fi
echo -e "  ${GREEN}✔${NC} System packages installed"

# ── Step 2: Download Bot Files ──────────────────────────────
echo -e "${BOLD}${BLUE}[2/7]${NC} Downloading bot files..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git checkout $BRANCH -q 2>/dev/null
    if ! git pull -q 2>/dev/null; then
        echo -e "  ${YELLOW}➤${NC} git pull failed, re-cloning..."
        cd /
        rm -rf "$INSTALL_DIR"
    fi
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
    rm -rf "$INSTALL_DIR"
    if git clone -b $BRANCH "https://github.com/${REPO}.git" "$INSTALL_DIR" 2>/dev/null; then
        cd "$INSTALL_DIR"
        echo -e "  ${GREEN}✔${NC} Bot files cloned from GitHub"
    else
        echo -e "  ${YELLOW}➤${NC} Git clone failed, downloading tarball..."
        if ! curl -fsSL "https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz" -o /tmp/bot.tar.gz; then
            echo -e "  ${RED}✘ Could not download files from GitHub — check network/URL${NC}"
            exit 1
        fi
        mkdir -p "$INSTALL_DIR"
        tar xzf /tmp/bot.tar.gz -C "$INSTALL_DIR" --strip-components=1
        rm -f /tmp/bot.tar.gz
        cd "$INSTALL_DIR"
        echo -e "  ${GREEN}✔${NC} Bot files downloaded"
    fi
else
    echo -e "  ${GREEN}✔${NC} Existing installation updated"
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "  ${RED}✘ Bot files are missing in $INSTALL_DIR (no requirements.txt)${NC}"
    exit 1
fi

# ── Step 3: Python Packages ─────────────────────────────────
echo -e "${BOLD}${BLUE}[3/7]${NC} Installing Python packages..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "  ${GREEN}✔${NC} Virtual environment created"
fi
$INSTALL_DIR/venv/bin/pip install --upgrade pip -q
if ! $INSTALL_DIR/venv/bin/pip install -r requirements.txt -q; then
    echo -e "  ${RED}✘ pip install failed. Try manually:${NC}"
    echo -e "      cd $INSTALL_DIR && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi
echo -e "  ${GREEN}✔${NC} Dependencies installed"

# ── Step 4: Management Command ──────────────────────────────
echo -e "${BOLD}${BLUE}[4/7]${NC} Setting up management command..."
chmod +x "$INSTALL_DIR/manage.sh" 2>/dev/null
ln -sf "$INSTALL_DIR/manage.sh" /usr/local/bin/nigvpn 2>/dev/null
echo -e "  ${GREEN}✔${NC} 'nigvpn' command available"

# ── Step 5: Configuration ───────────────────────────────────
echo -e "${BOLD}${BLUE}[5/7]${NC} Configuring..."
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
    echo -e "  ${YELLOW}➤${NC} Existing .env found. Press Enter to keep current value."
    echo ""
fi

read -p "  Bot Token: " BOT_TOKEN
BOT_TOKEN=${BOT_TOKEN:-$OLD_TOKEN}
if [ -z "$BOT_TOKEN" ]; then echo -e "  ${RED}✘ Bot Token is required!${NC}"; exit 1; fi

read -p "  Admin Telegram IDs: " ADMIN_IDS
ADMIN_IDS=${ADMIN_IDS:-$OLD_ADMIN}
if [ -z "$ADMIN_IDS" ]; then echo -e "  ${RED}✘ Admin IDs are required!${NC}"; exit 1; fi

read -p "  Web Panel Port [$OLD_PORT]: " WEB_PORT
WEB_PORT=${WEB_PORT:-${OLD_PORT:-5000}}
if ! echo "$WEB_PORT" | grep -qE '^[0-9]+$' || [ "$WEB_PORT" -lt 1 ] || [ "$WEB_PORT" -gt 65535 ]; then
    echo -e "  ${RED}✘ '${WEB_PORT}' is not a valid port (1-65535). Aborting.${NC}"
    exit 1
fi

read -p "  Admin Panel Username [$OLD_WEB_USER]: " ADMIN_WEB_USER
ADMIN_WEB_USER=${ADMIN_WEB_USER:-${OLD_WEB_USER:-admin}}

read -p "  Admin Panel Password [$OLD_WEB_PASS]: " ADMIN_WEB_PASS
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

echo -e "  ${GREEN}✔${NC} Configuration saved"

# ── Step 6: Systemd Service ─────────────────────────────────
echo -e "${BOLD}${BLUE}[6/7]${NC} Setting up service..."
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
echo -e "  ${GREEN}✔${NC} Service configured"

OLD_PID=$(lsof -ti:$WEB_PORT 2>/dev/null)
if [ -n "$OLD_PID" ]; then kill -9 $OLD_PID 2>/dev/null; fi

# ── Step 7: Start ───────────────────────────────────────────
echo -e "${BOLD}${BLUE}[7/7]${NC} Starting bot..."
systemctl restart ${SERVICE_NAME}
sleep 3

echo ""
if systemctl is-active --quiet ${SERVICE_NAME}; then
    PID=$(systemctl show ${SERVICE_NAME} --property=MainPID --value 2>/dev/null || echo "?")
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║  ${GREEN}✔ Installation Complete!${CYAN}                ║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  🌐 Web Panel: http://YOUR_IP:$WEB_PORT  ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  🔑 Login: ${CYAN}$ADMIN_WEB_USER${NC} / ${CYAN}$ADMIN_WEB_PASS${NC}       ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  📋 Logs: ${CYAN}tail -f $INSTALL_DIR/bot.log${NC} ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  🔧 Status: ${CYAN}systemctl status $SERVICE_NAME${NC} ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  🛠  Manager: ${CYAN}nigvpn${NC}                    ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
else
    echo -e "${BOLD}${RED}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${RED}║  ✘ Installation Failed!                  ║${NC}"
    echo -e "${BOLD}${RED}╚══════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}systemctl status:${NC}"
    systemctl status ${SERVICE_NAME} --no-pager -l 2>&1 | tail -20
    echo ""
    if [ -f "$INSTALL_DIR/bot.log" ] && [ -s "$INSTALL_DIR/bot.log" ]; then
        echo -e "${BOLD}Last lines of bot.log:${NC}"
        tail -30 "$INSTALL_DIR/bot.log"
    else
        echo -e "${YELLOW}bot.log is empty or missing.${NC} Try:"
        echo -e "  ${CYAN}journalctl -u $SERVICE_NAME -n 50 --no-pager${NC}"
    fi
    echo ""
    echo -e "  ${CYAN}Re-run: sudo bash <(curl -sL https://raw.githubusercontent.com/${REPO}/main/setup.sh)${NC}"
fi

echo ""
