#!/bin/bash
set -euo pipefail

INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while [ "$(ps -p $pid -o state= 2>/dev/null)" = "R" ]; do
        for (( i=0; i<${#spinstr}; i++ )); do
            printf "\r  ${CYAN}${spinstr:$i:1}${NC} %s" "$2"
            sleep $delay
        done
    done
    printf "\r"
}

step_done() {
    echo -e "  ${GREEN}✔${NC} $1"
}

step_fail() {
    echo -e "  ${RED}✘${NC} $1"
}

step_info() {
    echo -e "  ${YELLOW}➤${NC} $1"
}

clear
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║       NigVpn Bot Updater                 ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

cd "$INSTALL_DIR"

# ── Step 1: Backup ──────────────────────────────────────────
echo -e "${BOLD}${BLUE}[1/5]${NC} Backing up configuration..."
cp .env .env.bak 2>/dev/null || true
step_done "Config backed up"

# ── Step 2: Pull Code ───────────────────────────────────────
echo -e "${BOLD}${BLUE}[2/5]${NC} Pulling latest code..."

OLD_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "none")

if [ -d ".git" ]; then
    git fetch origin main -q 2>/dev/null
    NEW_COMMIT=$(git rev-parse --short origin/main 2>/dev/null || echo "unknown")
    
    if [ "$OLD_COMMIT" = "$NEW_COMMIT" ] && [ "$OLD_COMMIT" != "none" ]; then
        step_info "Already up to date (${CYAN}${OLD_COMMIT}${NC})"
    else
        OUTPUT=$(git pull origin main -q 2>&1) || true
        CHANGED=$(git diff --stat HEAD~1 HEAD 2>/dev/null | tail -1 || echo "")
        FILES_CHANGED=$(echo "$CHANGED" | grep -oP '\d+(?= file)' || echo "?")
        INSERTIONS=$(echo "$CHANGED" | grep -oP '\d+(?= insertion)' || echo "0")
        DELETIONS=$(echo "$CHANGED" | grep -oP '\d+(?= deletion)' || echo "0")
        
        if [ "$OLD_COMMIT" != "none" ] && [ "$OLD_COMMIT" != "$NEW_COMMIT" ]; then
            step_done "Updated: ${CYAN}${OLD_COMMIT}${NC} → ${GREEN}${NEW_COMMIT}${NC}"
            if [ "$FILES_CHANGED" != "?" ]; then
                echo -e "       ${YELLOW}📄${NC} ${FILES_CHANGED} files changed  ${GREEN}+${INSERTIONS}${NC}  ${RED}-${DELETIONS}${NC}"
            fi
        else
            step_done "Code updated to ${GREEN}${NEW_COMMIT}${NC}"
        fi
    fi
else
    step_info "Not a git repo. Re-downloading..."
    rm -rf "$INSTALL_DIR"
    git clone -b main https://github.com/ajavan034-coder/NigVpnBot.git "$INSTALL_DIR" 2>/dev/null
    cd "$INSTALL_DIR"
    step_done "Fresh clone complete"
fi

# Restore .env
cp .env.bak .env 2>/dev/null || true
rm -f .env.bak

# ── Step 3: Check Requirements ──────────────────────────────
echo -e "${BOLD}${BLUE}[3/5]${NC} Checking dependencies..."

REQ_HASH=$(md5sum requirements.txt 2>/dev/null | cut -d' ' -f1 || echo "new")
CACHED_HASH=$(cat .req_hash 2>/dev/null || echo "none")

if [ "$REQ_HASH" = "$CACHED_HASH" ]; then
    step_info "Dependencies unchanged, skipping install"
else
    step_info "Installing packages..."
    INSTALL_OUTPUT=$($INSTALL_DIR/venv/bin/pip install -q -r requirements.txt 2>&1)
    INSTALL_EXIT=$?
    echo "$REQ_HASH" > .req_hash
    
    if [ $INSTALL_EXIT -eq 0 ]; then
        NEW_PACKAGES=$(echo "$INSTALL_OUTPUT" | grep -c "Successfully installed" || echo "0")
        step_done "Dependencies updated"
    else
        step_fail "Package install had warnings (usually OK)"
    fi
fi

# ── Step 4: Database Migrations ─────────────────────────────
echo -e "${BOLD}${BLUE}[4/5]${NC} Checking database..."

if [ -f "bot_database.db" ]; then
    TABLES=$(sqlite3 bot_database.db ".tables" 2>/dev/null || echo "")
    if echo "$TABLES" | grep -q "collab_requests"; then
        step_info "Database schema up to date"
    else
        step_info "Running migrations (will happen on next bot start)"
    fi
else
    step_info "Database will be created on first start"
fi
step_done "Database check complete"

# ── Step 5: Restart ─────────────────────────────────────────
echo -e "${BOLD}${BLUE}[5/5]${NC} Restarting bot..."

systemctl restart "$SERVICE_NAME" 2>/dev/null

# Wait for startup
echo -ne "  ${CYAN}⠋${NC} Waiting for bot to start"
for i in {1..15}; do
    sleep 1
    echo -ne "."
done
echo ""

if systemctl is-active --quiet "$SERVICE_NAME"; then
    PID=$(systemctl show $SERVICE_NAME --property=MainPID --value 2>/dev/null || echo "?")
    MEM=$(ps -o rss= -p $PID 2>/dev/null | awk '{printf "%.1f", $1/1024}' || echo "?")
    UPTIME=$(ps -o etime= -p $PID 2>/dev/null | xargs || echo "?")
    
    step_done "Bot is ${GREEN}running${NC} (PID: ${CYAN}${PID}${NC})"
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║  ${GREEN}✔ Update Complete!${CYAN}                      ║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  📊 Status:  ${GREEN}Running${NC}                    ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  🆔 PID:     ${CYAN}${PID}${NC}                       ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  💾 Memory:  ${CYAN}${MEM} MB${NC}                    ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  ⏱  Uptime:  ${CYAN}${UPTIME}${NC}                     ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
else
    echo ""
    echo -e "${BOLD}${RED}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${RED}║  ✘ Update Failed!                        ║${NC}"
    echo -e "${BOLD}${RED}╠══════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${RED}║${NC}  Check logs:                             ${BOLD}${RED}║${NC}"
    echo -e "${BOLD}${RED}║${NC}  ${CYAN}tail -50 $INSTALL_DIR/bot.log${NC}          ${BOLD}${RED}║${NC}"
    echo -e "${BOLD}${RED}╚══════════════════════════════════════════╝${NC}"
fi

echo ""
