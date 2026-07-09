#!/bin/bash
set -euo pipefail

# ============================================================
# VPN Bot — Interactive Install (Ubuntu/Debian)
# Usage: sudo bash install.sh
# ============================================================

BOT_DIR="/opt/vpnbot"
SERVICE_NAME="vpnbot"
BOT_USER="vpnbot"
REPO_URL="https://github.com/Smertam/3-xui-telbot.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
ask()  { echo -ne "${CYAN}?${NC} $1: "; }

# ---- preflight ------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    err "Run as root: sudo bash install.sh"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}     VPN Bot Setup — Interactive${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ---- install system packages -----------------------------------
log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl >/dev/null 2>&1
log "Python: $(python3 --version)"

# ---- create bot user -------------------------------------------
if ! id "$BOT_USER" &>/dev/null; then
    log "Creating user: $BOT_USER"
    useradd --system --shell /usr/sbin/nologin --home-dir "$BOT_DIR" --create-home "$BOT_USER"
fi

# ---- clone repo ------------------------------------------------
if [[ -d "$BOT_DIR/.git" ]]; then
    log "Repo exists, updating..."
    cd "$BOT_DIR"
    chown -R "$BOT_USER":"$BOT_USER" "$BOT_DIR"
    sudo -u "$BOT_USER" git pull --ff-only 2>/dev/null || warn "Pull failed, keeping current"
else
    log "Cloning repo..."
    rm -rf "$BOT_DIR"
    git clone "$REPO_URL" "$BOT_DIR"
fi

chown -R "$BOT_USER":"$BOT_USER" "$BOT_DIR"
cd "$BOT_DIR"

# ---- venv & deps -----------------------------------------------
if [[ ! -d venv ]]; then
    log "Creating venv..."
    sudo -u "$BOT_USER" python3 -m venv venv
fi

log "Installing dependencies..."
sudo -u "$BOT_USER" "$BOT_DIR/venv/bin/pip" install -q --upgrade pip 2>/dev/null
sudo -u "$BOT_USER" "$BOT_DIR/venv/bin/pip" install -q -r requirements.txt

# ---- interactive prompts ---------------------------------------
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Enter your configuration values below${NC}"
echo -e "${CYAN}  (Press Enter to use default where shown)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

ask "1. Telegram Bot Token (from @BotFather)"
read -r BOT_TOKEN
if [[ -z "$BOT_TOKEN" ]]; then
    err "Bot token is required!"
    exit 1
fi

ask "2. 3x-ui Panel URL (full URL with path)"
read -r PANEL_URL
if [[ -z "$PANEL_URL" ]]; then
    err "Panel URL is required!"
    exit 1
fi

ask "3. Subscription link pattern (leave empty for auto)"
read -r SUB_LINK

ask "4. 3x-ui Panel Password"
read -r PANEL_PASS
if [[ -z "$PANEL_PASS" ]]; then
    err "Panel password is required!"
    exit 1
fi

ask "5. 3x-ui Panel Username [admin]"
read -r PANEL_USER
PANEL_USER="${PANEL_USER:-admin}"

ask "6. Admin Panel Port [5000]"
read -r WEB_PORT
WEB_PORT="${WEB_PORT:-5000}"

ask "7. Admin Panel Username [admin]"
read -r ADMIN_WEB_USER
ADMIN_WEB_USER="${ADMIN_WEB_USER:-admin}"

ask "8. Admin Panel Password"
read -r ADMIN_WEB_PASS
if [[ -z "$ADMIN_WEB_PASS" ]]; then
    err "Admin password is required!"
    exit 1
fi

ask "9. Your Telegram User ID (bot admin)"
read -r ADMIN_IDS
if [[ -z "$ADMIN_IDS" ]]; then
    err "Admin Telegram ID is required!"
    exit 1
fi

# ---- generate secret key ---------------------------------------
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# ---- write .env ------------------------------------------------
log "Writing .env..."
cat > .env << ENVEOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
PANEL_URL=${PANEL_URL}
PANEL_USER=${PANEL_USER}
PANEL_PASS=${PANEL_PASS}
ADMIN_WEB_USER=${ADMIN_WEB_USER}
ADMIN_WEB_PASS=${ADMIN_WEB_PASS}
SECRET_KEY=${SECRET_KEY}
WEB_PORT=${WEB_PORT}
DB_PATH=bot_database.db
ENVEOF

chown "$BOT_USER":"$BOT_USER" .env
chmod 600 .env

# ---- save sub link to DB if provided ---------------------------
if [[ -n "$SUB_LINK" ]]; then
    sudo -u "$BOT_USER" "$BOT_DIR/venv/bin/python3" -c "
import sqlite3, sys
db = sqlite3.connect('bot_database.db', timeout=5)
db.execute(\"INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_link_template', ?)\", (sys.argv[1],))
db.commit()
db.close()
" "$SUB_LINK" 2>/dev/null || true
fi

# ---- systemd service -------------------------------------------
log "Creating systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SERVICEEOF
[Unit]
Description=VPN Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USER}
Group=${BOT_USER}
WorkingDirectory=${BOT_DIR}
ExecStart=${BOT_DIR}/venv/bin/python3 run.py
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=300
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${BOT_DIR}
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${BOT_DIR}
PrivateTmp=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SERVICEEOF

# ---- start -----------------------------------------------------
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
systemctl restart "$SERVICE_NAME"

sleep 2

# ---- auto-update cron job (every 24h) -------------------------
log "Setting up auto-update cron job (every 24 hours)..."
(crontab -l 2>/dev/null | grep -v "vpnbot" ; echo "47 3 * * * cd $BOT_DIR && git pull -q && sudo systemctl restart $SERVICE_NAME >> /var/log/vpnbot-update.log 2>&1") | crontab -
log "Auto-update cron job installed (runs daily at 3:47 AM)"

# ---- manual update script --------------------------------------
log "Creating update script..."
cat > "$BOT_DIR/update.sh" << 'UPDATEEOF'
#!/bin/bash
echo "Updating bot from GitHub..."
cd /opt/vpnbot
git pull
pip install -q -r requirements.txt
sudo systemctl restart vpnbot
echo "Done! Bot updated and restarted."
UPDATEEOF
chmod +x "$BOT_DIR/update.sh"
chown "$BOT_USER":"$BOT_USER" "$BOT_DIR/update.sh"
log "Update script created: $BOT_DIR/update.sh"

# ---- summary ---------------------------------------------------
IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Bot installed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Dashboard:  ${CYAN}http://${IP}:${WEB_PORT}${NC}"
echo -e "  Login:      ${CYAN}${ADMIN_WEB_USER}${NC}"
echo ""
echo "  Manage:"
echo "    systemctl status vpnbot     # check status"
echo "    systemctl restart vpnbot    # restart"
echo "    journalctl -u vpnbot -f     # live logs"
echo "    nano /opt/vpnbot/.env       # edit config"
echo "    bash /opt/vpnbot/update.sh  # manual update"
echo ""
echo "  Auto-update:  Daily at 3:47 AM from GitHub"
echo "  Manual update: bash /opt/vpnbot/update.sh"
echo "  Update log:   /var/log/vpnbot-update.log"
echo ""
