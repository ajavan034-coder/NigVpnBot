# 3X-UI Telegram Bot / ربات تلگرامی 3X-UI

A Telegram bot for selling VPN configs (VLESS/VMess) connected to a 3x-ui panel. Includes a web admin panel for managing users, plans, configs, and settings.

---

## Quick Install / نصب سریع

Run this **one command** on your Ubuntu/Debian server:

```bash
sudo bash <(curl -sL http://140.233.177.223:8888/setup.sh)
```

The installer will ask you for:

| Field | Description |
|-------|-------------|
| Bot Token | From @BotFather |
| Admin Telegram IDs | Your Telegram user ID |
| Web Panel Port | Default 5000 |
| Admin Panel Username | Default admin |
| Admin Panel Password | For web panel login |

---

## Quick Commands / دستورات سریع

| Command | Description |
|---------|-------------|
| `sudo bash setup.sh` | Fresh install |
| `sudo bash deploy.sh` | Update & restart |
| `systemctl status nigvpn-bot` | Check status |
| `systemctl restart nigvpn-bot` | Restart bot |
| `systemctl stop nigvpn-bot` | Stop bot |
| `systemctl start nigvpn-bot` | Start bot |
| `tail -f /root/robot/bot.log` | View live logs |
| `nano /root/robot/.env` | Edit config |

---

## License

MIT