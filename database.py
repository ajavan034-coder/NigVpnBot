import aiosqlite
import json
from datetime import datetime, timedelta
from config import DB_PATH, ADMIN_IDS


async def get_db():
    db = await aiosqlite.connect(DB_PATH, timeout=10)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def init_db():
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

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
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
        "auto_approve_max": "0",
        "expiry_reminder_enabled": "1",
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


async def add_config(user_id: int, plan_id: int, sub_link: str, uuid: str, email: str, expire_date: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO configs (user_id, plan_id, sub_link, uuid, email, expire_date) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, plan_id, sub_link, uuid, email, expire_date),
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


async def add_receipt(user_id: int, amount: float, photo_file_id: str, plan_id: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO receipts (user_id, plan_id, amount, photo_file_id) VALUES (?, ?, ?, ?)",
        (user_id, plan_id, amount, photo_file_id),
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


async def add_plan(name: str, gb: int, days: int, price: int, inbound_ids: str = "", is_ultimate: bool = False) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO plans (name, gb, days, price, inbound_ids, is_ultimate) VALUES (?, ?, ?, ?, ?, ?)",
        (name, gb, days, price, inbound_ids, 1 if is_ultimate else 0),
    )
    plan_id = cursor.lastrowid
    await db.commit()
    await db.close()
    return plan_id


async def update_plan(plan_id: int, name: str = None, gb: int = None, days: int = None, price: int = None, is_active: bool = None, inbound_ids: str = None, is_ultimate: bool = None, section_id: int = None):
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
    if updates:
        values.append(plan_id)
        await db.execute(f"UPDATE plans SET {', '.join(updates)} WHERE id = ?", values)
        await db.commit()
    await db.close()


async def delete_plan(plan_id: int):
    db = await get_db()
    await db.execute("UPDATE plans SET is_active = 0 WHERE id = ?", (plan_id,))
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


async def get_plan_section(section_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plan_sections WHERE id = ?", (section_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def add_plan_section(name: str, display_order: int = 0) -> int:
    db = await get_db()
    cursor = await db.execute("INSERT INTO plan_sections (name, display_order) VALUES (?, ?)", (name, display_order))
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
