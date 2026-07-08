#!/bin/bash
set -euo pipefail

# ============================================================
# VPN Bot — Deploy Script (pull & restart)
# Usage: bash deploy.sh [git-branch]
# ============================================================

BOT_DIR="/opt/vpnbot"
SERVICE_NAME="vpnbot"
BRANCH="${1:-main}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

if [[ ! -d "$BOT_DIR/.git" ]]; then
    err "No git repo found at $BOT_DIR"
    exit 1
fi

cd "$BOT_DIR"

# ---- pre-deploy syntax check -----------------------------------
log "Checking Python syntax..."
SYNTAX_ERRORS=0
while IFS= read -r -d '' pyfile; do
    if ! python3 -m py_compile "$pyfile" 2>/dev/null; then
        err "Syntax error in: $pyfile"
        SYNTAX_ERRORS=1
    fi
done < <(find . -name "*.py" -not -path "./venv/*" -not -path "./__pycache__/*" -print0)

if [[ $SYNTAX_ERRORS -ne 1 ]]; then
    log "All Python files pass syntax check"
fi

# ---- backup critical files -------------------------------------
log "Backing up .env and database..."
cp .env .env.bak 2>/dev/null || true
cp bot_database.db bot_database.db.bak 2>/dev/null || true

# ---- pull latest code ------------------------------------------
log "Pulling latest code from origin/$BRANCH..."
if ! git pull --ff-only origin "$BRANCH"; then
    warn "Fast-forward failed. Trying git pull (may create merge commit)..."
    git pull origin "$BRANCH" || {
        err "Git pull failed. Restore backups and check manually."
        cp .env.bak .env 2>/dev/null || true
        cp bot_database.db.bak bot_database.db 2>/dev/null || true
        rm -f .env.bak bot_database.db.bak
        exit 1
    }
fi

# ---- restore critical files ------------------------------------
cp .env.bak .env 2>/dev/null || true
cp bot_database.db.bak bot_database.db 2>/dev/null || true
rm -f .env.bak bot_database.db.bak

# ---- update dependencies if requirements changed ---------------
if git diff HEAD~1 --name-only 2>/dev/null | grep -q "requirements.txt"; then
    log "requirements.txt changed — updating dependencies..."
    ./venv/bin/pip install -q -r requirements.txt
fi

# ---- restart service -------------------------------------------
log "Restarting $SERVICE_NAME..."
systemctl restart "$SERVICE_NAME"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Service is running!"
    systemctl status "$SERVICE_NAME" --no-pager -l
else
    err "Service failed to start. Checking logs..."
    journalctl -u "$SERVICE_NAME" --no-pager -n 30
    exit 1
fi
