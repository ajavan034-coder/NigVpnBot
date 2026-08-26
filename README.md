# NigVpnBot - VPN Telegram Bot

A Telegram bot for selling VPN configs connected to a 3x-ui panel, Azumi Wireguard Panel.

---

## Pre-configured Defaults / تنظیمات پیش‌فرض

Fresh installs are **not** a blank slate — the bot ships with a complete working
configuration (190+ settings) that seeds automatically on first boot:

- **Full Persian UI** — welcome message, all button labels/styles, bot texts,
  menu layout, premium emoji assignments
- **Sales catalog** — 3 plan sections + 12 ready plans (V2ray direct/tunnel tiers, WireGuard tiers)
- **Payment flow** — card-to-card instructions, wallet texts, top-up limits
- **Features enabled** — referral system (10% commission), collaboration requests,
  free test config, force-join channel, service monitoring

Secrets are **never** shipped. After install YOU must configure via the web panel:

| What | Where |
|------|-------|
| Bot token | asked during setup / web panel settings |
| Panel URL + credentials | web panel → تنظیمات |
| Card number & owner name | web panel → تنظیمات |
| Channel / notification IDs | web panel → تنظیمات |

Defaults live in `defaults/*.json`. They are inserted only if the key is missing —
your own changes are never overwritten on updates.

---

## Install / نصب

```bash
sudo bash <(curl -sL https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/setup.sh)
```
## Update / آپدیت

```bash
curl -sL https://raw.githubusercontent.com/ajavan034-coder/NigVpnBot/main/deploy.sh -o /tmp/deploy.sh && sudo bash /tmp/deploy.sh
```
## Open Consol Panel / باز کردن پنل
```bash
nigvpn
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
