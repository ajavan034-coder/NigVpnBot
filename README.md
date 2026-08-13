# 3X-UI Telegram Bot / ربات تلگرامی 3X-UI

A Telegram bot for selling VPN configs (VLESS/VMess) connected to a 3x-ui panel. Includes a web admin panel for managing users, plans, configs, and settings.

ربات تلگرامی برای فروش کانفیگ VPN (کارت به کارت و کیف پول) متصل به پنل 3x-ui. دارای پنل مدیریت وب برای مدیریت کاربران، پلن‌ها، کانفیگ‌ها و تنظیمات.

---

## Features / قابلیت‌ها

- Buy VPN config (card-to-card & wallet payment)
- Free test config
- My Services (QR code, sub link, volume info, change link)
- Buy extra volume
- Admin panel (users, plans, receipts, stats, settings)
- Button customization (emoji & style)
- Menu layout editor
- Bot text customization
- Force join channel
- New user & receipt notifications

- خرید کانفیگ VPN (کارت به کارت و کیف پول)
- کانفیگ رایگان تست
- سرویس‌های من (کد QR، لینک اشتراک، اطلاعات حجم، تغییر لینک)
- خرید حجم اضافه
- پنل مدیریت (کاربران، پلن‌ها، رسیدها، آمار، تنظیمات)
- سفارشی‌سازی دکمه‌ها (ایموجی و استایل)
- ویرایشگر لایوت منو
- سفارشی‌سازی متن‌های ربات
- اجبار به عضویت در کانال
- اعلان کاربر جدید و رسید

---

## Screenshots / اسکرین‌شات‌ها

### Bot Menu / منوی ربات
![Bot Menu](screenshots/bot_menu.png)

### Buy Config / خرید کانفیگ
![Buy Config](screenshots/buy_config.png)

### My Services / سرویس‌های من
![My Services](screenshots/my_services.png)

### Web Panel Dashboard / پنل مدیریت
![Web Panel](screenshots/web_panel.png)

### Settings Page / صفحه تنظیمات
![Settings](screenshots/settings.png)

---

## Quick Install / نصب سریع

Run this **one command** on your Ubuntu/Debian server:

این **یک دستور** را روی سرور خود (Ubuntu/Debian) اجرا کنید:

```bash
bash <(curl -sL https://raw.githubusercontent.com/Smertam/3-xui-telbot/main/setup.sh)
```

The installer will ask you for:

نصب‌کننده فقط از شما می‌پرسد:

| Field | Description |
|-------|-------------|
| Bot Token | From @BotFather |
| Admin Telegram IDs | Your Telegram user ID |
| Web Panel Port | Default 5000 |
| Admin Panel Username | Default admin |
| Admin Panel Password | For web panel login |

> All other settings (panel URL, channel, pricing) are preserved from your existing .env if updating, or use sensible defaults.

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

## Manual Install / نصب دستی

```bash
git clone -b main https://github.com/Smertam/3-xui-telbot.git /root/robot
cd /root/robot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
cp vpnbot.service /etc/systemd/system/nigvpn-bot.service
systemctl daemon-reload
systemctl enable nigvpn-bot
systemctl start nigvpn-bot
```

---

## Update / بروزرسانی

```bash
cd /root/robot
sudo bash deploy.sh
```

---

## Web Panel / پنل مدیریت

Access at `http://YOUR_IP:WEB_PORT`

---

## Tech Stack

- Python 3 + aiogram 3
- Flask (web admin panel)
- SQLite
- 3x-ui / Xray panel API
- systemd

---

## License

MIT