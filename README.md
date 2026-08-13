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

Run this on your Ubuntu/Debian server:

این دستور را روی سرور خود (Ubuntu/Debian) اجرا کنید:

```bash
git clone -b main https://github.com/Smertam/3-xui-telbot.git /tmp/robot-install && sudo bash /tmp/robot-install/setup.sh
```

> **Note:** If your repo is private, you'll be asked for your GitHub username and a Personal Access Token.
> Create one at: https://github.com/settings/tokens

> **توجه:** اگر رپازیت شما خصوصی است، نام کاربری GitHub و یک Personal Access Token از شما خواسته می‌شود.
> یکی بسازید در: https://github.com/settings/tokens

The installer will ask you for:

نصب‌کننده از شما می‌پرسد:

| Field | توضیح |
|-------|-------|
| Bot Token | From @BotFather / از @BotFather |
| Admin IDs | Your Telegram user ID / آیدی تلگرام شما |
| Channel ID | Notification channel (optional) / کانال اعلان (اختیاری) |
| Panel URL | 3x-ui panel URL / آدرس پنل 3x-ui |
| Panel User | Panel username / نام کاربری پنل |
| Panel Pass | Panel password / رمز پنل |
| Config Price | Default price / قیمت پیش‌فرض |
| Free Test Days | Trial duration / مدت تست رایگان |
| Config Months | Config duration / مدت اعتبار کانفیگ |
| Web Panel User | Admin panel login / نام کاربری پنل مدیریت |
| Web Panel Pass | Admin panel password / رمز پنل مدیریت |
| Web Panel Port | Default 5000 / پیش‌فرض 5000 |

---

## Quick Commands / دستورات سریع

| Command | Description | توضیح |
|---------|-------------|-------|
| `sudo bash setup.sh` | Fresh install | نصب جدید |
| `sudo bash deploy.sh` | Update & restart | بروزرسانی و ریستارت |
| `systemctl status nigvpn-bot` | Check status | بررسی وضعیت |
| `systemctl restart nigvpn-bot` | Restart bot | ریستارت ربات |
| `systemctl stop nigvpn-bot` | Stop bot | توقف ربات |
| `systemctl start nigvpn-bot` | Start bot | شروع ربات |
| `tail -f /root/robot/bot.log` | View live logs | مشاهده لاگ زنده |
| `nano /root/robot/.env` | Edit config | ویرایش تنظیمات |

---

## Manual Install / نصب دستی

```bash
git clone -b main https://github.com/Smertam/3-xui-telbot.git /root/robot
cd /root/robot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Fill in your credentials
```

Then install and start the service:

سرویس را نصب و شروع کنید:

```bash
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

Or manually:

یا دستی:

```bash
cd /root/robot
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart nigvpn-bot
```

---

## Web Panel / پنل مدیریت

Access at `http://YOUR_IP:WEB_PORT`

دسترسی از `http://YOUR_IP:WEB_PORT`

Manage: users, plans, configs, receipts, settings, bot texts, button styles, menu layout.

مدیریت: کاربران، پلن‌ها، کانفیگ‌ها، رسیدها، تنظیمات، متن‌های ربات، استایل دکمه‌ها، لایوت منو.

---

## Tech Stack / تکنولوژی‌ها

- Python 3 + aiogram 3
- Flask (web admin panel)
- SQLite (bot_database.db)
- 3x-ui / Xray panel API
- systemd (process management)

---

## License / لایسنس

MIT