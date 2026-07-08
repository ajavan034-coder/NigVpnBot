#!/bin/bash
set -euo pipefail

# ============================================================
# VPN Bot — One-Command Install (Ubuntu/Debian)
# Usage: sudo bash install.sh
# ============================================================

BOT_DIR="/opt/vpnbot"
SERVICE_NAME="vpnbot"
BOT_USER="vpnbot"
REPO_URL="https://github.com/Smertam/3-xui-telbot.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- preflight ------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    err "Run as root: sudo bash install.sh"
    exit 1
fi

if [[ ! -f /etc/debian_version ]]; then
    err "Debian/Ubuntu only"
    exit 1
fi

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

# ---- .env from example -----------------------------------------
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
    else
        cat > .env << 'ENVEOF'
BOT_TOKEN=
ADMIN_IDS=
PANEL_URL=
PANEL_USER=
PANEL_PASS=
ADMIN_WEB_USER=admin
ADMIN_WEB_PASS=admin
SECRET_KEY=
WEB_PORT=5000
DB_PATH=bot_database.db
ENVEOF
    fi
    chown "$BOT_USER":"$BOT_USER" .env
    chmod 600 .env
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

# ---- summary ---------------------------------------------------
echo ""
echo "============================================"
echo -e "${GREEN}  Bot installed successfully!${NC}"
echo "============================================"
echo ""
echo "  Next step: open in browser"
echo ""
IP=$(hostname -I | awk '{print $1}')
echo -e "  ${GREEN}http://${IP}:5000${NC}"
echo ""
echo "  The setup wizard will guide you."
echo ""
