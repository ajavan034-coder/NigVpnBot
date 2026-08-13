# NigVpnBot - VPN Telegram Bot

A Telegram bot for selling VPN configs (VLESS/VMess) connected to a 3x-ui panel.

---

## Install / نصب

```bash
curl -sL https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/setup.sh -o /tmp/setup.sh && sudo bash /tmp/setup.sh
```

You'll be asked for:
- Bot Token (from @BotFather)
- Admin Telegram IDs
- Web Panel Port (default 5000)
- Admin Panel Username
- Admin Panel Password

---

## Commands / دستورات

| Command | Description |
|---------|-------------|
| `sudo bash setup.sh` | Fresh install |
| `sudo bash deploy.sh` | Update & restart |
| `systemctl status nigvpn-bot` | Check status |
| `systemctl restart nigvpn-bot` | Restart bot |
| `tail -f /root/robot/bot.log` | View logs |

---

## License

MIT
