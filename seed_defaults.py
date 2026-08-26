"""Seed fresh installations with the full default configuration.

Reads defaults/default_settings.json and defaults/default_plans.json.
Safe semantics:
  - settings: inserted ONLY if the key does not exist yet (never overwrites)
  - plan_sections/plans: seeded only when BOTH tables are completely empty

Secrets (bot token, panel credentials, card number, personal chat IDs)
are intentionally NOT part of the shipped defaults.
"""
import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DEFAULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defaults")


def _load(name: str):
    path = os.path.join(DEFAULTS_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_str(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def seed_all(db_path: str) -> dict:
    """Apply shipped defaults to a database. Returns counts of inserted rows."""
    stats = {"settings_seeded": 0, "sections_seeded": 0, "plans_seeded": 0}

    conn = sqlite3.connect(db_path, timeout=10)
    try:
        # ── settings: insert-if-absent ──
        settings = _load("default_settings.json")
        if settings:
            existing = {r[0] for r in conn.execute("SELECT key FROM settings").fetchall()}
            new_keys = [k for k in settings if k not in existing]
            for key in new_keys:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    (key, _to_str(settings[key])),
                )
            stats["settings_seeded"] = len(new_keys)

        # ── plan catalog: only for a completely fresh install ──
        catalog = _load("default_plans.json")
        if catalog:
            sections_empty = conn.execute("SELECT COUNT(*) FROM plan_sections").fetchone()[0] == 0
            plans_empty = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0
            if sections_empty and plans_empty:
                sid_map = []
                for section in catalog.get("plan_sections", []):
                    cur = conn.execute(
                        "INSERT INTO plan_sections (name, display_order) VALUES (?, ?)",
                        (section["name"], section.get("display_order", 0)),
                    )
                    sid_map.append(cur.lastrowid)
                    stats["sections_seeded"] += 1

                for plan in catalog.get("plans", []):
                    idx = plan.get("section_index")
                    section_id = (
                        sid_map[idx]
                        if idx is not None and 0 <= idx < len(sid_map)
                        else None
                    )
                    conn.execute(
                        "INSERT INTO plans (name, gb, days, price, is_active, is_ultimate, "
                        "section_id, collaborator_price, ip_limit, service_type) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            plan["name"],
                            plan["gb"],
                            plan["days"],
                            plan["price"],
                            1 if plan.get("is_active") else 0,
                            1 if plan.get("is_ultimate") else 0,
                            section_id,
                            plan.get("collaborator_price", 0),
                            plan.get("ip_limit", 0),
                            plan.get("service_type", "v2ray"),
                        ),
                    )
                    stats["plans_seeded"] += 1

        if any(stats.values()):
            conn.commit()
        return stats
    finally:
        conn.close()
