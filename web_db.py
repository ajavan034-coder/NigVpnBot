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


def get_new_users_today():
    conn = get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE created_at LIKE ? || '%'", (today,)
    ).fetchone()
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
            "SELECT * FROM users WHERE CAST(id AS TEXT) = ? OR username LIKE ? OR first_name LIKE ? ORDER BY created_at DESC",
            (search, f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_users_page(page=1, per_page=25, search=None):
    """Paginated users list. Returns (users, total, pages)."""
    conn = get_conn()
    where, params = "", []
    if search:
        where = "WHERE CAST(id AS TEXT) = ? OR username LIKE ? OR first_name LIKE ?"
        params = [search, f"%{search}%", f"%{search}%"]
    total = conn.execute(f"SELECT COUNT(*) as cnt FROM users {where}", params).fetchone()["cnt"]
    pages = max(1, -(-total // per_page))
    page = max(1, min(page, pages))
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows], total, pages


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
    rows = conn.execute(
        "SELECT p.*, s.name AS section_name FROM plans p "
        "LEFT JOIN plan_sections s ON p.section_id = s.id "
        "ORDER BY s.display_order, p.price"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_plan(name, gb, days, price, inbound_ids="", is_ultimate=False, collaborator_price=0, section_id=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO plans (name, gb, days, price, inbound_ids, is_ultimate, collaborator_price, section_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, gb, days, price, inbound_ids, 1 if is_ultimate else 0, collaborator_price, section_id),
    )
    plan_id = cur.lastrowid
    conn.commit()
    conn.close()
    return plan_id


def update_plan(plan_id, name=None, gb=None, days=None, price=None, is_active=None, inbound_ids=None, is_ultimate=None, section_id=None, collaborator_price=None):
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
    if collaborator_price is not None:
        updates.append("collaborator_price = ?")
        values.append(collaborator_price)
    if updates:
        values.append(plan_id)
        conn.execute(f"UPDATE plans SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_plan(plan_id):
    conn = get_conn()
    conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
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


def get_receipts(status=None, limit=50, page=None, per_page=None):
    conn = get_conn()
    where, params = "", []
    if status and status != "all":
        where = "WHERE r.status = ?"
        params.append(status)
    if page is not None and per_page is not None:
        total = conn.execute(
            f"SELECT COUNT(*) as cnt FROM receipts r {where}", params
        ).fetchone()["cnt"]
        pages = max(1, -(-total // per_page))
        page = max(1, min(page, pages))
        rows = conn.execute(
            f"SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
            f"{where} ORDER BY r.created_at DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows], total, pages
    rows = conn.execute(
        "SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
        f"{where} ORDER BY r.created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_receipts_by_status():
    conn = get_conn()
    rows = conn.execute("SELECT status, COUNT(*) as cnt FROM receipts GROUP BY status").fetchall()
    conn.close()
    return {r["status"]: r["cnt"] for r in rows}


def get_user_configs(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM configs WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_configs(limit=100, page=None, per_page=None):
    conn = get_conn()
    if page is not None and per_page is not None:
        total = conn.execute("SELECT COUNT(*) as cnt FROM configs").fetchone()["cnt"]
        pages = max(1, -(-total // per_page))
        page = max(1, min(page, pages))
        rows = conn.execute(
            "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id "
            "ORDER BY c.created_at DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows], total, pages
    rows = conn.execute(
        "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def activate_config(config_id):
    conn = get_conn()
    conn.execute("UPDATE configs SET is_active = 1 WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()


def get_recent_receipts(limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id "
        "ORDER BY r.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_panels_overview():
    """All panels with aggregated purchase stats (config counts + purchased GB)."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.url, p.is_active, p.is_default, p.created_at,
               p.volume_gb, p.panel_type, p.free_test_enabled, p.free_test_mb,
               p.free_test_days, p.inbound_ids,
               COALESCE(s.config_count, 0)   AS config_count,
               COALESCE(s.active_configs, 0) AS active_configs,
               COALESCE(s.purchased_gb, 0)   AS purchased_gb
        FROM panels p
        LEFT JOIN (
            SELECT c.panel_id AS pid,
                   COUNT(*)                                        AS config_count,
                   SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_configs,
                   COALESCE(SUM(pl.gb), 0)                          AS purchased_gb
            FROM configs c
            LEFT JOIN plans pl ON c.plan_id = pl.id
            GROUP BY c.panel_id
        ) s ON s.pid = p.id
        ORDER BY p.is_default DESC, p.id
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_panel_purchase_totals():
    """Global totals across all panels for summary cards."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(pl.gb), 0) AS total_gb, COUNT(*) AS total_configs
        FROM configs c LEFT JOIN plans pl ON c.plan_id = pl.id
        """
    ).fetchone()
    active = conn.execute("SELECT COUNT(*) AS cnt FROM configs WHERE is_active = 1").fetchone()["cnt"]
    conn.close()
    return {"total_gb": row["total_gb"], "total_configs": row["total_configs"], "active_configs": active}


def get_unattributed_purchases():
    """Configs whose panel_id is NULL or points at a deleted panel (legacy data)."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT COUNT(*) AS config_count,
               COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0) AS active_configs,
               COALESCE(SUM(pl.gb), 0) AS purchased_gb
        FROM configs c
        LEFT JOIN plans pl ON c.plan_id = pl.id
        WHERE c.panel_id IS NULL
           OR c.panel_id NOT IN (SELECT id FROM panels)
        """
    ).fetchone()
    conn.close()
    return dict(row)


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


# ── Earnings / Charts ──────────────────────────────────────────────


def get_monthly_revenue(months=12):
    conn = get_conn()
    rows = conn.execute(
        "SELECT strftime('%Y-%m', created_at) as month, "
        "COUNT(*) as count, COALESCE(SUM(amount), 0) as total "
        "FROM receipts WHERE status = 'approved' "
        "GROUP BY month ORDER BY month DESC LIMIT ?",
        (months,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_daily_revenue(days=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT date(created_at) as day, "
        "COUNT(*) as count, COALESCE(SUM(amount), 0) as total "
        "FROM receipts WHERE status = 'approved' "
        "AND created_at >= date('now', ?) "
        "GROUP BY day ORDER BY day",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_revenue():
    conn = get_conn()
    this_week = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
        "FROM receipts WHERE status = 'approved' "
        "AND created_at >= date('now', 'weekday 0', '-7 days')",
    ).fetchone()
    last_week = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
        "FROM receipts WHERE status = 'approved' "
        "AND created_at >= date('now', 'weekday 0', '-14 days') "
        "AND created_at < date('now', 'weekday 0', '-7 days')",
    ).fetchone()
    conn.close()
    return {
        "this_week": dict(this_week) if this_week else {"total": 0, "count": 0},
        "last_week": dict(last_week) if last_week else {"total": 0, "count": 0},
    }


def get_revenue_by_status():
    conn = get_conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) as count, COALESCE(SUM(amount), 0) as total "
        "FROM receipts GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: {"count": r["count"], "total": r["total"]} for r in rows}


def get_today_revenue():
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
        "FROM receipts WHERE status = 'approved' AND date(created_at) = date('now')"
    ).fetchone()
    conn.close()
    return dict(row) if row else {"total": 0, "count": 0}


def get_pending_amount():
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
        "FROM receipts WHERE status = 'pending'"
    ).fetchone()
    conn.close()
    return dict(row) if row else {"total": 0, "count": 0}
