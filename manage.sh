#!/bin/bash

INSTALL_DIR="/root/robot"
SERVICE_NAME="nigvpn-bot"
BACKUP_DIR="/root/robot_backups"
SSL_DOMAIN=""
WEB_PORT=$(grep WEB_PORT "$INSTALL_DIR/.env" 2>/dev/null | cut -d= -f2)
WEB_PORT=${WEB_PORT:-5000}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear_screen() { clear; }

show_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}${BOLD}        NigVpn Bot Manager Panel          ${NC}${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "  Status: ${GREEN}● Running${NC}"
    else
        echo -e "  Status: ${RED}● Stopped${NC}"
    fi
    echo ""
}

show_menu() {
    echo -e "  ${BOLD}[1]${NC} Start Bot"
    echo -e "  ${BOLD}[2]${NC} Stop Bot"
    echo -e "  ${BOLD}[3]${NC} Restart Bot"
    echo -e "  ${BOLD}[4]${NC} Backup"
    echo -e "  ${BOLD}[5]${NC} Restore Backup"
    echo -e "  ${BOLD}[6]${NC} SSL Certificate & Nginx Setup"
    echo -e "  ${BOLD}[7]${NC} View Logs"
    echo -e "  ${BOLD}[8]${NC} Edit .env"
    echo -e "  ${BOLD}[9]${NC} ${GREEN}⬆  Update Bot${NC}"
    echo -e "  ${BOLD}[0]${NC} Exit"
    echo ""
}

do_start() {
    echo -e "\n${YELLOW}Starting bot...${NC}"
    systemctl start "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Bot started successfully!${NC}"
    else
        echo -e "${RED}Failed to start bot. Check: tail -20 $INSTALL_DIR/bot.log${NC}"
    fi
}

do_stop() {
    echo -e "\n${YELLOW}Stopping bot...${NC}"
    systemctl stop "$SERVICE_NAME"
    sleep 1
    echo -e "${GREEN}Bot stopped.${NC}"
}

do_restart() {
    echo -e "\n${YELLOW}Restarting bot...${NC}"
    systemctl restart "$SERVICE_NAME"
    sleep 3
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Bot restarted successfully!${NC}"
    else
        echo -e "${RED}Failed to restart. Check: tail -20 $INSTALL_DIR/bot.log${NC}"
    fi
}

do_backup() {
    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

    echo -e "\n${YELLOW}Creating backup...${NC}"
    tar czf "$BACKUP_FILE" \
        -C "$(dirname $INSTALL_DIR)" \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.git' \
        --exclude='bot.log*' \
        "$(basename $INSTALL_DIR)" 2>/dev/null

    if [ -f "$BACKUP_FILE" ]; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo -e "${GREEN}Backup created!${NC}"
        echo -e "  File: ${BOLD}$BACKUP_FILE${NC}"
        echo -e "  Size: $SIZE"
        echo ""
        echo -e "${CYAN}All backups:${NC}"
        ls -lh "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
    else
        echo -e "${RED}Backup failed!${NC}"
    fi
}

do_restore() {
    echo -e "\n${CYAN}Available backups:${NC}"
    echo ""

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls $BACKUP_DIR/backup_*.tar.gz 2>/dev/null)" ]; then
        echo -e "${RED}No backups found in $BACKUP_DIR${NC}"
        return
    fi

    BACKUPS=($(ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null))

    for i in "${!BACKUPS[@]}"; do
        FILE="${BACKUPS[$i]}"
        SIZE=$(du -h "$FILE" | cut -f1)
        DATE=$(basename "$FILE" .tar.gz | sed 's/backup_//' | sed 's/_/ /')
        echo -e "  ${BOLD}[$((i+1))]${NC} $DATE ($SIZE)"
    done
    echo ""

    read -p "Select backup number (0 to cancel): " CHOICE

    if [ "$CHOICE" = "0" ] || [ -z "$CHOICE" ]; then
        echo -e "${YELLOW}Cancelled.${NC}"
        return
    fi

    if [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt "${#BACKUPS[@]}" ] 2>/dev/null; then
        echo -e "${RED}Invalid selection.${NC}"
        return
    fi

    SELECTED="${BACKUPS[$((CHOICE-1))]}"
    echo -e "\n${YELLOW}Restoring from: $(basename $SELECTED)${NC}"
    read -p "This will overwrite current files. Continue? (y/n): " CONFIRM

    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo -e "${YELLOW}Cancelled.${NC}"
        return
    fi

    # Stop bot
    systemctl stop "$SERVICE_NAME" 2>/dev/null

    # Backup current .env
    cp "$INSTALL_DIR/.env" /tmp/.env.backup 2>/dev/null

    # Restore
    tar xzf "$SELECTED" -C "$(dirname $INSTALL_DIR)" 2>/dev/null

    # Restore .env
    cp /tmp/.env.backup "$INSTALL_DIR/.env" 2>/dev/null
    rm -f /tmp/.env.backup

    # Restart
    systemctl start "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Backup restored and bot started!${NC}"
    else
        echo -e "${RED}Restore done but bot failed to start. Check logs.${NC}"
    fi
}

do_ssl() {
    echo -e "\n${CYAN}═══ SSL Certificate & Nginx Setup ═══${NC}"
    echo ""

    # Get domain
    read -p "Enter your domain (e.g., bot.example.com): " DOMAIN
    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}Domain is required!${NC}"
        return
    fi

    # Get email for Let's Encrypt
    read -p "Enter email for SSL certificate: " EMAIL
    if [ -z "$EMAIL" ]; then
        echo -e "${RED}Email is required!${NC}"
        return
    fi

    echo -e "\n${YELLOW}[1/5] Installing Nginx...${NC}"
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y -qq nginx certbot python3-certbot-nginx > /dev/null 2>&1

    echo -e "${YELLOW}[2/5] Configuring Nginx...${NC}"
    cat > /etc/nginx/sites-available/nigvpn <<NGINX
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
NGINX

    ln -sf /etc/nginx/sites-available/nigvpn /etc/nginx/sites-enabled/nigvpn
    rm -f /etc/nginx/sites-enabled/default

    echo -e "${YELLOW}[3/5] Testing Nginx config...${NC}"
    nginx -t 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "${RED}Nginx config test failed!${NC}"
        return
    fi

    systemctl restart nginx
    systemctl enable nginx > /dev/null 2>&1

    echo -e "${YELLOW}[4/5] Obtaining SSL certificate...${NC}"
    certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}[5/5] Setting up auto-renewal...${NC}"
        (crontab -l 2>/dev/null; echo "0 0,12 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
        echo -e "${GREEN}SSL certificate installed successfully!${NC}"
        echo ""
        echo -e "  Domain:  ${BOLD}https://$DOMAIN${NC}"
        echo -e "  Web App: ${BOLD}https://$DOMAIN/app${NC}"
        echo -e "  Panel:   ${BOLD}https://$DOMAIN${NC}"
    else
        echo -e "${RED}SSL certificate failed. Make sure DNS points to this server.${NC}"
    fi
}

do_logs() {
    echo -e "\n${CYAN}═══ Recent Logs (last 30 lines) ═══${NC}\n"
    tail -30 "$INSTALL_DIR/bot.log" 2>/dev/null || echo -e "${RED}No log file found.${NC}"
    echo ""
    read -p "Press Enter to continue..."
}

do_edit_env() {
    echo -e "\n${CYAN}═══ Editing .env ═══${NC}"
    echo -e "  Current .env location: ${BOLD}$INSTALL_DIR/.env${NC}"
    echo ""
    read -p "Press Enter to open editor..."
    nano "$INSTALL_DIR/.env"
    echo -e "\n${YELLOW}Restarting bot to apply changes...${NC}"
    systemctl restart "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Bot restarted with new config!${NC}"
    else
        echo -e "${RED}Bot failed to start. Check .env for errors.${NC}"
    fi
}

do_update() {
    echo -e "\n${CYAN}═══ Updating Bot ═══${NC}"
    echo ""

    cd "$INSTALL_DIR"

    # Check if git repo
    if [ ! -d ".git" ]; then
        echo -e "${RED}Not a git repository. Reinstalling...${NC}"
        bash <(curl -s https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/setup.sh)
        return
    fi

    # Save current state
    OLD_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

    # Fetch latest
    echo -e "  ${YELLOW}➤${NC} Fetching latest changes..."
    git fetch origin main -q 2>/dev/null
    NEW_COMMIT=$(git rev-parse --short origin/main 2>/dev/null || echo "unknown")

    if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
        echo -e "  ${GREEN}✔${NC} Already up to date (${CYAN}${OLD_COMMIT}${NC})"
        echo ""
        return
    fi

    # Show what changed
    echo -e "  ${YELLOW}➤${NC} Updating: ${CYAN}${OLD_COMMIT}${NC} → ${GREEN}${NEW_COMMIT}${NC}"
    echo ""

    # Backup .env
    cp .env .env.bak 2>/dev/null || true

    # Pull
    git pull origin main -q 2>/dev/null

    # Restore .env
    cp .env.bak .env 2>/dev/null || true
    rm -f .env.bak

    # Show diff stats
    CHANGED=$(git diff --stat ${OLD_COMMIT}..${NEW_COMMIT} 2>/dev/null | tail -1 || echo "")
    if [ -n "$CHANGED" ]; then
        FILES_CHANGED=$(echo "$CHANGED" | grep -oP '\d+(?= file)' || echo "?")
        INSERTIONS=$(echo "$CHANGED" | grep -oP '\d+(?= insertion)' || echo "0")
        DELETIONS=$(echo "$CHANGED" | grep -oP '\d+(?= deletion)' || echo "0")
        echo -e "  📄 ${FILES_CHANGED} files changed  ${GREEN}+${INSERTIONS}${NC}  ${RED}-${DELETIONS}${NC}"
    fi

    # Update packages
    echo -e "  ${YELLOW}➤${NC} Updating Python packages..."
    $INSTALL_DIR/venv/bin/pip install -q -r requirements.txt 2>/dev/null
    echo -e "  ${GREEN}✔${NC} Packages updated"

    # Restart
    echo -e "  ${YELLOW}➤${NC} Restarting bot..."
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        PID=$(systemctl show $SERVICE_NAME --property=MainPID --value 2>/dev/null || echo "?")
        echo ""
        echo -e "  ${GREEN}✔ Update successful!${NC} (PID: ${CYAN}${PID}${NC})"
    else
        echo ""
        echo -e "  ${RED}✘ Bot failed to start after update.${NC}"
        echo -e "  Check logs: ${CYAN}tail -20 $INSTALL_DIR/bot.log${NC}"
    fi
}

# Main loop
while true; do
    clear_screen
    show_header
    show_menu
    read -p "  Select option: " OPTION
    echo ""

    case $OPTION in
        1) do_start ;;
        2) do_stop ;;
        3) do_restart ;;
        4) do_backup ;;
        5) do_restore ;;
        6) do_ssl ;;
        7) do_logs ;;
        8) do_edit_env ;;
        9) do_update ;;
        0) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
        *) echo -e "${RED}Invalid option.${NC}" ;;
    esac

    echo ""
    read -p "  Press Enter to continue..."
done
