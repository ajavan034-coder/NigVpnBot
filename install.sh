#!/bin/bash
set -euo pipefail

# ============================================================
# VPN Bot — Fresh Install Script (Ubuntu/Debian)
# Usage: sudo bash install.sh
# ============================================================

BOT_DIR="/opt/vpnbot"
SERVICE_NAME="vpnbot"
BOT_USER="vpnbot"
REPO_URL="${REPO_URL:-}"  # Set via env or edit here

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- preflight ------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (use sudo)"
    exit 1
fi

if [[ ! -f /etc/debian_version ]]; then
    err "This script supports Debian/Ubuntu only"
    exit 1
fi

# ---- install system packages -----------------------------------
log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl >/dev/null

PYTHON_MAJOR=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Python version: $PYTHON_MAJOR"

# ---- create bot user -------------------------------------------
if ! id "$BOT_USER" &>/dev/null; then
    log "Creating system user: $BOT_USER"
    useradd --system --shell /usr/sbin/nologin --home-dir "$BOT_DIR" --create-home "$BOT_USER"
else
    log "User $BOT_USER already exists"
fi

# ---- clone or copy repo ----------------------------------------
if [[ -d "$BOT_DIR/.git" ]]; then
    log "Repository already exists at $BOT_DIR, pulling latest..."
    cd "$BOT_DIR"
    sudo -u "$BOT_USER" git pull --ff-only || warn "git pull failed, keeping current version"
else
    if [[ -n "$REPO_URL" ]]; then
        log "Cloning repository..."
        sudo -u "$BOT_USER" git clone "$REPO_URL" "$BOT_DIR"
    else
        log "No REPO_URL set. Copying current directory to $BOT_DIR..."
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        mkdir -p "$BOT_DIR"
        cp -r "$SCRIPT_DIR"/* "$SCRIPT_DIR"/.* "$BOT_DIR" 2>/dev/null || true
        chown -R "$BOT_USER":"$BOT_USER" "$BOT_DIR"
    fi
fi

cd "$BOT_DIR"

# ---- create venv & install deps --------------------------------
if [[ ! -d venv ]]; then
    log "Creating Python virtual environment..."
    sudo -u "$BOT_USER" python3 -m venv venv
fi

log "Installing Python dependencies..."
sudo -u "$BOT_USER" "$BOT_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$BOT_USER" "$BOT_DIR/venv/bin/pip" install -q -r requirements.txt

# ---- create .env from example ----------------------------------
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        chown "$BOT_USER":"$BOT_USER" .env
        chmod 600 .env
        warn "Created .env from .env.example — EDIT IT with your real values!"
    else
        warn "No .env file found. Create one with: cp .env.example .env && nano .env"
    fi
fi

# ---- set permissions -------------------------------------------
chown -R "$BOT_USER":"$BOT_USER" "$BOT_DIR"
chmod 600 .env 2>/dev/null || true

# ---- create systemd service ------------------------------------
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

# Environment
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${BOT_DIR}

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${BOT_DIR}
PrivateTmp=true

# Logging (journald)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SERVICEEOF

# ---- enable & start --------------------------------------------
log "Enabling and starting service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# ---- summary ---------------------------------------------------
sleep 2
echo ""
echo "============================================"
echo -e "${GREEN}  VPN Bot installed successfully!${NC}"
echo "============================================"
echo ""
echo "  Service:  $SERVICE_NAME"
echo "  Location: $BOT_DIR"
echo "  User:     $BOT_USER"
echo ""
echo "  Commands:"
echo "    systemctl status $SERVICE_NAME    # check status"
echo "    systemctl restart $SERVICE_NAME   # restart bot"
echo "    journalctl -u $SERVICE_NAME -f    # live logs"
echo "    nano $BOT_DIR/.env                # edit config"
echo ""
echo "  Web dashboard: http://YOUR_IP:5000"
echo ""
systemctl status "$SERVICE_NAME" --no-pager -l || true
