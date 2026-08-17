import aiosqlite
import json
from datetime import datetime, timedelta
from config import DB_PATH, ADMIN_IDS
import logging
import time

logger = logging.getLogger(__name__)


async def get_db():
    db = await aiosqlite.connect(DB_PATH, timeout=10)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def _check_db_integrity():
    """Check DB integrity at startup and attempt recovery."""
    import sqlite3, os, shutil
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] != 'ok':
            logger.error(f"Database corruption detected: {result[0]}")
            backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"db_backup_{int(time.time())}.db")
            shutil.copy2(db_path, backup_path)
            logger.info(f"Corrupted DB backed up to {backup_path}")
    except Exception as e:
        logger.error(f"DB integrity check failed: {e}")


async def init_db():
    await _check_db_integrity()
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            invite_code TEXT,
            referred_by INTEGER
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER,
            sub_link TEXT,
            uuid TEXT,
            email TEXT,
            expire_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER DEFAULT 0,
            amount REAL,
            photo_file_id TEXT,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gb INTEGER NOT NULL,
            days INTEGER NOT NULL,
            price INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            inbound_ids TEXT DEFAULT '',
            is_ultimate INTEGER DEFAULT 0,
            section_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS plan_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            display_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            user_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            sub_link_template TEXT DEFAULT '',
            inbound_ids TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    for col in ["invite_code", "referred_by"]:
        try:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT" if col == "invite_code" else f"ALTER TABLE users ADD COLUMN {col} INTEGER")
        except Exception:
            pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN inbound_ids TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN is_ultimate INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN section_id INTEGER")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN ip_limit INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN panel_id INTEGER")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE configs ADD COLUMN panel_id INTEGER")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE panels ADD COLUMN volume_gb INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE configs ADD COLUMN config_name TEXT")

        try:
            await db.execute("ALTER TABLE receipts ADD COLUMN channel_sent INTEGER DEFAULT 0")
        except Exception:
            pass
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE receipts ADD COLUMN config_name TEXT")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE receipts ADD COLUMN discount_code TEXT")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE receipts ADD COLUMN discount_amount REAL DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plan_sections ADD COLUMN panel_id INTEGER")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN service_type TEXT DEFAULT 'v2ray'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE panels ADD COLUMN panel_type TEXT DEFAULT 'v2ray'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE panels ADD COLUMN free_test_enabled INTEGER DEFAULT 0")
        await db.execute("ALTER TABLE panels ADD COLUMN free_test_mb INTEGER DEFAULT 102400")
        await db.execute("ALTER TABLE panels ADD COLUMN free_test_days INTEGER DEFAULT 1")
        await db.execute("ALTER TABLE panels ADD COLUMN free_test_inbound_ids TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE panels ADD COLUMN emoji_id TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT NOT NULL DEFAULT 'percent',
                discount_value REAL NOT NULL,
                max_uses INTEGER DEFAULT 0,
                used_count INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                plan_id INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collab_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by INTEGER
            )
        """)
    except Exception:
        pass

    # ── New tables from SpeedyBot features ──────────────────────
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                type TEXT NOT NULL,
                description TEXT DEFAULT '',
                unique_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guide_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                media_type TEXT DEFAULT 'TEXT',
                body TEXT DEFAULT '',
                file_id TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS service_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_email TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(service_email, event_type)
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                max_uses INTEGER DEFAULT 1,
                uses INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                admin_msg_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass

    try:
        await db.execute("ALTER TABLE users ADD COLUMN is_collaborator INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE plans ADD COLUMN collaborator_price INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN phone_verified_at TIMESTAMP")
    except Exception:
        pass
    await db.commit()

    for admin_id in ADMIN_IDS:
        existing = await db.execute("SELECT user_id FROM admins WHERE user_id = ?", (admin_id,))
        if not await existing.fetchone():
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))

    defaults = {
        "welcome_text": "به NigVpn خوش آمدید! خرید آسان و امن VPN",
        "currency": "IRR",
        "currency_symbol": "تومان",
        "min_topup": "50000",
        "btn_wallet": "\U0001f4b3 Wallet",
        "btn_free_test": "\U0001f195 Free Test",
        "btn_buy_config": "\U0001f6d2 Buy Config",
        "btn_my_configs": "\U0001f4cb سرویس‌های من",
        "btn_topup": "\U0001f4b5 Top Up",
        "btn_tx_history": "\U0001f4ca History",
        "btn_back": "\u2b05\ufe0f Back",
        "btn_back_to_menu": "\u2b05\ufe0f Menu",
        "btn_admin_stats": "\U0001f4ca Statistics",
        "btn_admin_receipts": "\U0001f4cb Receipts",
        "btn_admin_users": "\U0001f465 Users",
        "btn_admin_settings": "\u2699\ufe0f Settings",
        "btn_admin_admins": "\U0001f511 Admins",
        "btn_admin_plans": "\U0001f4c8 Plans",
        "card_number": "1234-5678-9012-3456",
        "card_owner": "Card Owner Name",
        "btn_c2c_payment": "\U0001f4b3 کارت به کارت",
        "btn_wallet_payment": "\U0001f4b0 Pay with Wallet",
        "c2c_title": "\U0001f4b3 **Card to Card Payment**",
        "c2c_instruction": "Send the exact amount to the card below, then upload your payment receipt.",
        "free_test_mb": "102400",
        "free_test_enabled": "1",
        "free_test_days": "1",
        "free_test_inbound_ids": "",
        "auto_approve_max": "0",
        "expiry_reminder_enabled": "1",
        "invite_enabled": "0",
        "invite_reward_amount": "5000",
        "text_invite": "",
        "force_join_enabled": "0",
        "required_channel_id": "",
        "force_join_text": "⚠️ برای استفاده از ربات، ابتدا باید در کانال ما عضو شوید!",
        "force_join_fail_text": "❌ شما هنوز در کانال عضو نیستید! لطفاً ابتدا عضو شوید و سپس دوباره بررسی کنید.",
        "force_join_btn_join": "🔗 عضویت در کانال",
        "force_join_btn_check": "✅ بررسی عضویت",
        "panel_url": "",
        "panel_user": "",
        "panel_pass": "",
        "sub_link_template": "",
        "inbound_id": "",
        "extra_volume_price_per_gb": "6000",
        "notification_channel_id": "",
        "text_new_user_notification": "",
        "text_free_test_notification": "",
        "text_new_config_notification": "",
        "text_receipt_notification": "",
        "collab_enabled": "1",
        "collab_notification_channel": "",
        "btn_collab_request": "🤝 درخواست همکاری",
        "backup_enabled": "1",
        "backup_hour": "4",
        "backup_minute": "0",
        "shop_open": "1",
        "shop_close_message": "فروش به دلیل بروزرسانی موقتاً بسته شده است.",
        "operating_mode": "NORMAL",
        "phone_verification_enabled": "0",
        "cashback_percent": "0",
        "service_monitor_enabled": "0",
        "service_monitor_interval": "300",
        "volume_warning_percent": "80",
        "expiry_warning_hours": "48",
        "maintenance_message": "🔧 ربات در حال بروزرسانی است. لطفاً بعداً تلاش کنید.",
        "sales_paused_message": "⛔ فروش موقتاً متوقف شده است.",
        "btn_redeem_gift": "🎁 کد هدیه",
        "btn_guides": "📖 راهنمای اتصال",
    }
    for key, value in defaults.items():
        existing = await db.execute("SELECT key FROM settings WHERE key = ?", (key,))
        if not await existing.fetchone():
            await db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))

    plan_exists = await db.execute("SELECT COUNT(*) as cnt FROM plans")
    if (await plan_exists.fetchone())["cnt"] == 0:
        default_plans = [
            ("1 Month", 50, 30, 150000),
            ("3 Months", 100, 90, 350000),
            ("6 Months", 200, 180, 600000),
        ]
        for name, gb, days, price in default_plans:
            await db.execute(
                "INSERT INTO plans (name, gb, days, price) VALUES (?, ?, ?, ?)",
                (name, gb, days, price),
            )

    await db.commit()
    await db.close()


async def get_setting(key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    await db.close()
    return row["value"] if row else None


async def set_setting(key: str, value: str):
    db = await get_db()
    await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    await db.commit()
    await db.close()


async def add_user(user_id: int, username: str | None, first_name: str | None) -> bool:
    import secrets
    db = await get_db()
    cursor = await db.execute(
        "INSERT OR IGNORE INTO users (id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name),
    )
    is_new = cursor.rowcount > 0
    if is_new:
        code = secrets.token_urlsafe(8)
        await db.execute("UPDATE users SET invite_code = ? WHERE id = ?", (code, user_id))
    await db.commit()
    await db.close()
    return is_new


async def get_user(user_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def update_balance(user_id: int, amount: float):
    db = await get_db()
    await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    await db.commit()
    await db.close()


async def get_balance(user_id: int) -> float:
    db = await get_db()
    cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    await db.close()
    return row["balance"] if row else 0.0


async def set_banned(user_id: int, banned: bool):
    db = await get_db()
    await db.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))
    await db.commit()
    await db.close()


async def get_user_by_invite_code(code: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE invite_code = ?", (code,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def set_referred_by(user_id: int, referrer_id: int):
    db = await get_db()
    await db.execute("UPDATE users SET referred_by = ? WHERE id = ?", (referrer_id, user_id))
    await db.commit()
    await db.close()


async def get_invite_stats(user_id: int) -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT invite_code FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    code = row["invite_code"] if row else None
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (user_id,))
    cnt = (await cursor.fetchone())["cnt"]
    await db.close()
    return {"code": code, "count": cnt}


async def search_users(query: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM users WHERE id = ? OR username LIKE ? LIMIT 10",
        (query, f"%{query}%"),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_all_users() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_user_count() -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"]


async def get_user_count_by_period(days: int = 0) -> int:
    db = await get_db()
    if days > 0:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM users WHERE created_at >= ?", (since,))
    else:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"]


async def get_config_count() -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM configs WHERE is_active = 1")
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"]


async def get_total_revenue() -> float:
    db = await get_db()
    cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM receipts WHERE status = 'approved'")
    row = await cursor.fetchone()
    await db.close()
    return row["total"]


async def has_free_test(user_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM configs WHERE user_id = ? AND email LIKE '%free%'",
        (user_id,),
    )
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"] > 0


async def reset_free_test(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM configs WHERE user_id = ? AND email LIKE '%free%'",
        (user_id,),
    )
    await db.commit()
    await db.close()


async def get_free_test_users() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT DISTINCT c.user_id, u.username, u.first_name, c.created_at, c.email
           FROM configs c
           LEFT JOIN users u ON c.user_id = u.id
           WHERE c.email LIKE '%free%'
           ORDER BY c.created_at DESC"""
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    return rows


async def get_unsent_receipts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM receipts WHERE channel_sent = 0 AND photo_file_id IS NOT NULL ORDER BY created_at ASC"
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    return rows


async def mark_receipt_sent(receipt_id: int):
    db = await get_db()
    await db.execute("UPDATE receipts SET channel_sent = 1 WHERE id = ?", (receipt_id,))
    await db.commit()
    await db.close()


async def reset_all_free_tests() -> int:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM configs WHERE email LIKE '%free%'"
    )
    count = cursor.rowcount
    await db.commit()
    await db.close()
    return count


async def add_config(user_id: int, plan_id: int, sub_link: str, uuid: str, email: str, expire_date: str, panel_id: int = None, config_name: str = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO configs (user_id, plan_id, sub_link, uuid, email, expire_date, panel_id, config_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, plan_id, sub_link, uuid, email, expire_date, panel_id, config_name),
    )
    await db.commit()
    await db.close()


async def get_user_configs(user_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM configs WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_active_configs(user_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM configs WHERE user_id = ? AND is_active = 1 AND expire_date > ? ORDER BY expire_date",
        (user_id, datetime.utcnow().isoformat()),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def deactivate_config(config_id: int):
    db = await get_db()
    await db.execute("UPDATE configs SET is_active = 0 WHERE id = ?", (config_id,))
    await db.commit()
    await db.close()


async def delete_config(config_id: int):
    db = await get_db()
    await db.execute("DELETE FROM configs WHERE id = ?", (config_id,))
    await db.commit()
    await db.close()


async def get_expired_active_configs() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM configs WHERE is_active = 1 AND expire_date < ?",
        (datetime.utcnow().isoformat(),),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_configs_expiring_soon() -> list[dict]:
    from datetime import timedelta
    soon = (datetime.utcnow() + timedelta(days=2)).isoformat()
    now = datetime.utcnow().isoformat()
    db = await get_db()
    cursor = await db.execute(
        "SELECT c.*, u.username FROM configs c JOIN users u ON c.user_id = u.id "
        "WHERE c.is_active = 1 AND c.expire_date > ? AND c.expire_date < ?",
        (now, soon),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def add_receipt(user_id: int, amount: float, photo_file_id: str, plan_id: int = 0, config_name: str = "") -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO receipts (user_id, plan_id, amount, photo_file_id, config_name) VALUES (?, ?, ?, ?, ?)",
        (user_id, plan_id, amount, photo_file_id, config_name),
    )
    receipt_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return receipt_id


async def get_pending_receipts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT r.*, u.username FROM receipts r JOIN users u ON r.user_id = u.id WHERE r.status = 'pending' ORDER BY r.created_at"
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_receipt(receipt_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def approve_receipt(receipt_id: int, admin_id: int):
    db = await get_db()
    receipt = await get_receipt(receipt_id)
    if receipt:
        await db.execute(
            "UPDATE receipts SET status = 'approved', admin_id = ?, processed_at = ? WHERE id = ?",
            (admin_id, datetime.utcnow().isoformat(), receipt_id),
        )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (receipt["amount"], receipt["user_id"]),
        )
        await db.commit()
    await db.close()


async def reject_receipt(receipt_id: int, admin_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE receipts SET status = 'rejected', admin_id = ?, processed_at = ? WHERE id = ?",
        (admin_id, datetime.utcnow().isoformat(), receipt_id),
    )
    await db.commit()
    await db.close()


async def add_admin(user_id: int, username: str | None):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
    await db.commit()
    await db.close()


async def remove_admin(user_id: int):
    db = await get_db()
    await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    await db.commit()
    await db.close()


async def is_admin(user_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    await db.close()
    return row is not None


async def get_admins() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM admins")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_plans() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plans WHERE is_active = 1 ORDER BY price")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_all_plans() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plans ORDER BY price")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_plan(plan_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def add_plan(name: str, gb: int, days: int, price: int, inbound_ids: str = "", is_ultimate: bool = False, ip_limit: int = 0, panel_id: int = None, service_type: str = "v2ray", collaborator_price: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO plans (name, gb, days, price, inbound_ids, is_ultimate, ip_limit, panel_id, service_type, collaborator_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, gb, days, price, inbound_ids, 1 if is_ultimate else 0, ip_limit, panel_id, service_type, collaborator_price),
    )
    plan_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return plan_id


async def update_plan(plan_id: int, name: str = None, gb: int = None, days: int = None, price: int = None, is_active: bool = None, inbound_ids: str = None, is_ultimate: bool = None, section_id: int = None, ip_limit: int = None, panel_id: int = None, service_type: str = None, collaborator_price: int = None):
    db = await get_db()
    updates = []
    values = []
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if gb is not None:
        updates.append("gb = ?")
        values.append(gb)
    if days is not None:
        updates.append("days = ?")
        values.append(days)
    if price is not None:
        updates.append("price = ?")
        values.append(price)
    if is_active is not None:
        updates.append("is_active = ?")
        values.append(1 if is_active else 0)
    if inbound_ids is not None:
        updates.append("inbound_ids = ?")
        values.append(inbound_ids)
    if is_ultimate is not None:
        updates.append("is_ultimate = ?")
        values.append(1 if is_ultimate else 0)
    if section_id is not None:
        updates.append("section_id = ?")
        values.append(section_id)
    if ip_limit is not None:
        updates.append("ip_limit = ?")
        values.append(ip_limit)
    if panel_id is not None:
        updates.append("panel_id = ?")
        values.append(panel_id)
    if service_type is not None:
        updates.append("service_type = ?")
        values.append(service_type)
    if collaborator_price is not None:
        updates.append("collaborator_price = ?")
        values.append(collaborator_price)
    if updates:
        values.append(plan_id)
        await db.execute(f"UPDATE plans SET {', '.join(updates)} WHERE id = ?", values)
        await db.commit()
    await db.close()


async def delete_plan(plan_id: int):
    db = await get_db()
    await db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    await db.commit()
    await db.close()


async def update_config_sub_link(config_id: int, new_sub_link: str):
    db = await get_db()
    await db.execute("UPDATE configs SET sub_link = ? WHERE id = ?", (new_sub_link, config_id))
    await db.commit()
    await db.close()


async def get_config_by_id(config_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM configs WHERE id = ?", (config_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_plan_name(plan_id: int) -> str:
    if not plan_id:
        return "تست رایگان"
    plan = await get_plan(plan_id)
    return plan["name"] if plan else "نامشخص"


async def get_plan_sections() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plan_sections ORDER BY display_order, id")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_plan_sections_by_panel(panel_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plan_sections WHERE panel_id = ? ORDER BY display_order, id", (panel_id,))
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_plan_section(section_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plan_sections WHERE id = ?", (section_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def add_plan_section(name: str, display_order: int = 0, panel_id: int = None) -> int:
    db = await get_db()
    cursor = await db.execute("INSERT INTO plan_sections (name, display_order, panel_id) VALUES (?, ?, ?)", (name, display_order, panel_id))
    section_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return section_id


async def update_plan_section(section_id: int, name: str = None, display_order: int = None):
    db = await get_db()
    updates, values = [], []
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if display_order is not None:
        updates.append("display_order = ?")
        values.append(display_order)
    if updates:
        values.append(section_id)
        await db.execute(f"UPDATE plan_sections SET {', '.join(updates)} WHERE id = ?", values)
        await db.commit()
    await db.close()


async def delete_plan_section(section_id: int):
    db = await get_db()
    await db.execute("UPDATE plans SET section_id = NULL WHERE section_id = ?", (section_id,))
    await db.execute("DELETE FROM plan_sections WHERE id = ?", (section_id,))
    await db.commit()
    await db.close()


# ==================== Panel CRUD ====================

async def add_panel(name: str, url: str, username: str, password: str, sub_link_template: str = "", inbound_ids: str = "", is_default: bool = False, volume_gb: int = 0, panel_type: str = "v2ray", free_test_enabled: int = 0, free_test_mb: int = 102400, free_test_days: int = 1, free_test_inbound_ids: str = "", emoji_id: str = "") -> int:
    db = await get_db()
    if is_default:
        await db.execute("UPDATE panels SET is_default = 0")
    cursor = await db.execute(
        "INSERT INTO panels (name, url, username, password, sub_link_template, inbound_ids, is_default, volume_gb, panel_type, free_test_enabled, free_test_mb, free_test_days, free_test_inbound_ids, emoji_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, url, username, password, sub_link_template, inbound_ids, 1 if is_default else 0, volume_gb, panel_type, free_test_enabled, free_test_mb, free_test_days, free_test_inbound_ids, emoji_id),
    )
    panel_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return panel_id


async def get_panel(panel_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM panels WHERE id = ?", (panel_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_all_panels() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM panels ORDER BY is_default DESC, name")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_active_panels() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM panels WHERE is_active = 1 ORDER BY is_default DESC, name")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def update_panel(panel_id: int, **kwargs):
    db = await get_db()
    updates, values = [], []
    for key, value in kwargs.items():
        if key in ("name", "url", "username", "password", "sub_link_template", "inbound_ids", "is_active", "is_default", "panel_type", "free_test_enabled", "free_test_mb", "free_test_days", "free_test_inbound_ids", "emoji_id"):
            updates.append(f"{key} = ?")
            values.append(value)
    if updates:
        values.append(panel_id)
        await db.execute(f"UPDATE panels SET {', '.join(updates)} WHERE id = ?", values)
        await db.commit()
    await db.close()


async def delete_panel(panel_id: int):
    db = await get_db()
    await db.execute("DELETE FROM panels WHERE id = ?", (panel_id,))
    await db.commit()
    await db.close()


async def set_default_panel(panel_id: int):
    db = await get_db()
    await db.execute("UPDATE panels SET is_default = 0")
    await db.execute("UPDATE panels SET is_default = 1 WHERE id = ?", (panel_id,))
    await db.commit()
    await db.close()


async def get_default_panel() -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM panels WHERE is_default = 1 AND is_active = 1 LIMIT 1")
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_configs_by_panel(panel_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM configs WHERE panel_id = ? ORDER BY created_at DESC", (panel_id,))
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_plans_by_panel(panel_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plans WHERE panel_id = ? ORDER BY price", (panel_id,))
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_configs_count_by_panel(panel_id: int) -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM configs WHERE panel_id = ?", (panel_id,))
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"] if row else 0


async def get_plans_count_by_panel(panel_id: int) -> int:
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM plans WHERE panel_id = ?", (panel_id,))
    row = await cursor.fetchone()
    await db.close()
    return row["cnt"] if row else 0


# ── Discount Codes ─────────────────────────────────────────────
async def add_discount_code(code: str, discount_type: str, discount_value: float,
                            max_uses: int = 0, expires_at: str = None, plan_id: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO discount_codes (code, discount_type, discount_value, max_uses, expires_at, plan_id) VALUES (?, ?, ?, ?, ?, ?)",
        (code.upper(), discount_type, discount_value, max_uses, expires_at, plan_id),
    )
    row_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return row_id


async def get_discount_code(code: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM discount_codes WHERE code = ?", (code.upper(),))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_discount_code_by_id(code_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM discount_codes WHERE id = ?", (code_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def use_discount_code(code_id: int):
    db = await get_db()
    await db.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE id = ?", (code_id,))
    await db.commit()
    await db.close()


async def delete_discount_code(code_id: int):
    db = await get_db()
    await db.execute("DELETE FROM discount_codes WHERE id = ?", (code_id,))
    await db.commit()
    await db.close()


async def get_all_discount_codes() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


# ==================== Collaboration Requests ====================

async def add_collab_request(user_id: int, message: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO collab_requests (user_id, message) VALUES (?, ?)",
        (user_id, message),
    )
    request_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return request_id


async def get_collab_request(request_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM collab_requests WHERE id = ?", (request_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_pending_collab_requests() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT cr.*, u.username, u.first_name FROM collab_requests cr "
        "LEFT JOIN users u ON cr.user_id = u.id "
        "WHERE cr.status = 'pending' ORDER BY cr.created_at DESC"
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def update_collab_request(request_id: int, status: str, reviewed_by: int):
    db = await get_db()
    await db.execute(
        "UPDATE collab_requests SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), reviewed_by, request_id),
    )
    await db.commit()
    await db.close()


async def set_user_collaborator(user_id: int, is_collaborator: bool):
    db = await get_db()
    await db.execute("UPDATE users SET is_collaborator = ? WHERE id = ?", (1 if is_collaborator else 0, user_id))
    await db.commit()
    await db.close()


# ==================== Blacklist ====================

async def is_blacklisted(user_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
    result = await cursor.fetchone()
    await db.close()
    return result is not None

async def add_to_blacklist(user_id: int, reason: str = "") -> None:
    db = await get_db()
    await db.execute("INSERT OR REPLACE INTO blacklist (user_id, reason) VALUES (?, ?)", (user_id, reason))
    await db.commit()
    await db.close()

async def remove_from_blacklist(user_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
    await db.commit()
    await db.close()

async def get_blacklisted_users() -> list:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM blacklist")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


# ==================== Wallet Transaction Ledger ====================

async def wallet_credit(user_id: int, amount: float, tx_type: str, description: str = "", unique_key: str = None) -> bool:
    """Credit wallet with idempotent unique_key. Returns True if applied."""
    db = await get_db()
    if unique_key:
        existing = await db.execute("SELECT 1 FROM wallet_transactions WHERE unique_key = ?", (unique_key,))
        if await existing.fetchone():
            await db.close()
            return False
    await db.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    balance_after = row["balance"] if row else 0
    await db.execute(
        "INSERT INTO wallet_transactions (user_id, amount, balance_after, type, description, unique_key) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, amount, balance_after, tx_type, description, unique_key),
    )
    await db.commit()
    await db.close()
    return True


async def wallet_debit(user_id: int, amount: float, tx_type: str, description: str = "", unique_key: str = None) -> bool:
    """Debit wallet. Returns True if applied, False if insufficient balance or duplicate."""
    db = await get_db()
    if unique_key:
        existing = await db.execute("SELECT 1 FROM wallet_transactions WHERE unique_key = ?", (unique_key,))
        if await existing.fetchone():
            await db.close()
            return False
    cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row or row["balance"] < amount:
        await db.close()
        return False
    await db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    balance_after = row["balance"] if row else 0
    await db.execute(
        "INSERT INTO wallet_transactions (user_id, amount, balance_after, type, description, unique_key) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, -amount, balance_after, tx_type, description, unique_key),
    )
    await db.commit()
    await db.close()
    return True


async def get_wallet_history(user_id: int, limit: int = 20) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


# ==================== Service Notifications ====================

async def has_service_notification(service_email: str, event_type: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM service_notifications WHERE service_email = ? AND event_type = ?",
        (service_email, event_type),
    )
    result = await cursor.fetchone()
    await db.close()
    return result is not None


async def add_service_notification(service_email: str, user_id: int, event_type: str) -> bool:
    """Returns True if inserted (not duplicate)."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO service_notifications (service_email, user_id, event_type) VALUES (?, ?, ?)",
            (service_email, user_id, event_type),
        )
        await db.commit()
        await db.close()
        return True
    except Exception:
        await db.close()
        return False


# ==================== Guide Items ====================

async def add_guide_item(platform: str, media_type: str = "TEXT", body: str = "", file_id: str = "") -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO guide_items (platform, media_type, body, file_id) VALUES (?, ?, ?, ?)",
        (platform, media_type, body, file_id),
    )
    item_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return item_id


async def get_guides_by_platform(platform: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM guide_items WHERE platform = ? AND active = 1 ORDER BY sort_order, id",
        (platform,),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def get_all_guides() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM guide_items ORDER BY platform, sort_order, id")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def delete_guide_item(guide_id: int):
    db = await get_db()
    await db.execute("DELETE FROM guide_items WHERE id = ?", (guide_id,))
    await db.commit()
    await db.close()


async def toggle_guide_item(guide_id: int):
    db = await get_db()
    await db.execute("UPDATE guide_items SET active = NOT active WHERE id = ?", (guide_id,))
    await db.commit()
    await db.close()


# ==================== Gift Codes ====================

async def add_gift_code(code: str, amount: float, max_uses: int = 1, expires_at: str = None) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO gift_codes (code, amount, max_uses, expires_at) VALUES (?, ?, ?, ?)",
        (code.upper(), amount, max_uses, expires_at),
    )
    row_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return row_id


async def get_gift_code(code: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM gift_codes WHERE code = ?", (code.upper(),))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def get_gift_code_by_id(code_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM gift_codes WHERE id = ?", (code_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def redeem_gift_code(code: str, user_id: int) -> float:
    """Try to redeem a gift code. Returns amount if success, 0 if failed."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM gift_codes WHERE code = ? AND active = 1", (code.upper(),))
    row = await cursor.fetchone()
    if not row:
        await db.close()
        return 0
    gift = dict(row)
    if gift["expires_at"]:
        from datetime import datetime
        if datetime.fromisoformat(gift["expires_at"]) < datetime.utcnow():
            await db.close()
            return 0
    if gift["uses"] >= gift["max_uses"]:
        await db.close()
        return 0
    await db.execute("UPDATE gift_codes SET uses = uses + 1 WHERE code = ?", (code.upper(),))
    await db.execute(
        "INSERT INTO gift_redemptions (code, user_id, amount) VALUES (?, ?, ?)",
        (code.upper(), user_id, gift["amount"]),
    )
    await db.commit()
    await db.close()
    return gift["amount"]


async def get_all_gift_codes() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM gift_codes ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


async def delete_gift_code(code_id: int):
    db = await get_db()
    await db.execute("DELETE FROM gift_codes WHERE id = ?", (code_id,))
    await db.commit()
    await db.close()


async def toggle_gift_code(code_id: int):
    db = await get_db()
    await db.execute("UPDATE gift_codes SET active = NOT active WHERE id = ?", (code_id,))
    await db.commit()
    await db.close()


# ==================== Support Messages ====================

async def store_support_message(admin_msg_id: int, user_id: int):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO support_messages (admin_msg_id, user_id) VALUES (?, ?)",
        (admin_msg_id, user_id),
    )
    await db.commit()
    await db.close()


async def get_support_user(admin_msg_id: int) -> int | None:
    db = await get_db()
    cursor = await db.execute("SELECT user_id FROM support_messages WHERE admin_msg_id = ?", (admin_msg_id,))
    row = await cursor.fetchone()
    await db.close()
    return row["user_id"] if row else None
