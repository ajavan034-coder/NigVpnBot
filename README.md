# NigVpnBot - VPN Telegram Bot

A Telegram bot for selling VPN configs connected to a 3x-ui panel, Azumi Wireguard Panel.

---

## Install / نصب

```bash
sudo bash <(curl -sL https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/setup.sh)
```
## Update / آپدیت

```bash
curl -sL https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/deploy.sh -o /tmp/deploy.sh && sudo bash /tmp/deploy.sh
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
