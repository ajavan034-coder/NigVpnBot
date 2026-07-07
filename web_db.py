import sqlite3
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_user_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row["cnt"]


def get_config_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM configs WHERE is_active = 1").fetchone()
    conn.close()
    return row["cnt"]


def get_total_revenue():
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM receipts WHERE status = 'approved'").fetchone()
    conn.close()
    return row["total"]


def get_pending_receipt_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM receipts WHERE status = 'pending'").fetchone()
    conn.close()
    return row["cnt"]


def get_all_users(search=None):
    conn = get_conn()
    if search:
        rows = conn.execute(
            "SELECT * FROM users WHERE id = ? OR username LIKE ? OR first_name LIKE ? ORDER BY created_at DESC",
            (search, f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_balance(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def set_banned(user_id, banned):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()


def get_all_plans():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM plans ORDER BY price").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_plan(name, gb, days, price, inbound_ids="", is_ultimate=False):
    conn = get_conn()
    cur = conn.execute("INSERT INTO plans (name, gb, days, price, inbound_ids, is_ultimate) VALUES (?, ?, ?, ?, ?, ?)", (name, gb, days, price, inbound_ids, 1 if is_ultimate else 0))
    plan_id = cur.lastrowid
    conn.commit()
    conn.close()
    return plan_id


def update_plan(plan_id, name=None, gb=None, days=None, price=None, is_active=None, inbound_ids=None, is_ultimate=None, section_id=None):
    conn = get_conn()
    updates, values = [], []
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
        conn.execute(f"UPDATE plans SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_plan(plan_id):
    conn = get_conn()
    conn.execute("UPDATE plans SET is_active = 0 WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()


def get_pending_receipts():
    conn = get_conn()
    rows = conn.execute(
        "SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
        "WHERE r.status = 'pending' ORDER BY r.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_receipt(receipt_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def approve_receipt(receipt_id, admin_id=0):
    conn = get_conn()
    receipt = dict(conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone() or {})
    if receipt:
        conn.execute(
            "UPDATE receipts SET status = 'approved', admin_id = ?, processed_at = ? WHERE id = ?",
            (admin_id, datetime.utcnow().isoformat(), receipt_id),
        )
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (receipt["amount"], receipt["user_id"]),
        )
        conn.commit()
    conn.close()


def reject_receipt(receipt_id, admin_id=0):
    conn = get_conn()
    conn.execute(
        "UPDATE receipts SET status = 'rejected', admin_id = ?, processed_at = ? WHERE id = ?",
        (admin_id, datetime.utcnow().isoformat(), receipt_id),
    )
    conn.commit()
    conn.close()


def get_receipts(status=None, limit=50):
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
            "WHERE r.status = ? ORDER BY r.created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
            "ORDER BY r.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_configs(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM configs WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_configs(limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deactivate_config(config_id):
    conn = get_conn()
    conn.execute("UPDATE configs SET is_active = 0 WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()


def delete_config(config_id):
    conn = get_conn()
    conn.execute("DELETE FROM configs WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()


def get_admins():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM admins").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_admin(user_id, username=None):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()


def remove_admin(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_plan_sections():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM plan_sections ORDER BY display_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan_section(section_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM plan_sections WHERE id = ?", (section_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_plan_section(name, display_order=0):
    conn = get_conn()
    cur = conn.execute("INSERT INTO plan_sections (name, display_order) VALUES (?, ?)", (name, display_order))
    section_id = cur.lastrowid
    conn.commit()
    conn.close()
    return section_id


def update_plan_section(section_id, name=None, display_order=None):
    conn = get_conn()
    updates, values = [], []
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if display_order is not None:
        updates.append("display_order = ?")
        values.append(display_order)
    if updates:
        values.append(section_id)
        conn.execute(f"UPDATE plan_sections SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_plan_section(section_id):
    conn = get_conn()
    conn.execute("UPDATE plans SET section_id = NULL WHERE section_id = ?", (section_id,))
    conn.execute("DELETE FROM plan_sections WHERE id = ?", (section_id,))
    conn.commit()
    conn.close()
