"""Environment validation — run before bot startup to catch config errors."""

import os
import sys
import re
import socket


def _check(label: str, ok: bool, msg: str = ""):
    status = "OK" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    return ok


def validate_env() -> bool:
    print("\nEnvironment validation:")
    all_ok = True

    # BOT_TOKEN
    token = os.getenv("BOT_TOKEN", "")
    all_ok &= _check(
        "BOT_TOKEN",
        bool(token) and re.match(r"^\d+:[A-Za-z0-9_-]+$", token),
        "Must look like 123456789:ABCdef..." if not token else "",
    )

    # ADMIN_IDS
    raw_ids = os.getenv("ADMIN_IDS", "")
    ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
    all_ok &= _check(
        "ADMIN_IDS",
        all(x.isdigit() for x in ids) if ids else False,
        "Comma-separated numeric IDs required",
    )

    # PANEL_URL
    panel_url = os.getenv("PANEL_URL", "")
    if panel_url:
        match = re.match(r"https?://([^:/]+)(?::(\d+))?", panel_url)
        if match:
            host = match.group(1)
            port = int(match.group(2)) if match.group(2) else (443 if panel_url.startswith("https") else 80)
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()
                all_ok &= _check("PANEL_URL", True, f"Reachable ({host}:{port})")
            except (socket.timeout, OSError) as e:
                all_ok &= _check("PANEL_URL", False, f"Cannot reach {host}:{port} — {e}")
        else:
            all_ok &= _check("PANEL_URL", False, "Invalid URL format")
    else:
        _check("PANEL_URL", True, "Not set (optional)")

    # WEB_PORT
    web_port = os.getenv("WEB_PORT", "5000")
    all_ok &= _check("WEB_PORT", web_port.isdigit() and 1 <= int(web_port) <= 65535, f"Value: {web_port}")

    # SECRET_KEY
    secret = os.getenv("SECRET_KEY", "")
    all_ok &= _check("SECRET_KEY", len(secret) >= 16, "Should be at least 16 characters")

    # DB_PATH
    db_path = os.getenv("DB_PATH", "bot_database.db")
    db_dir = os.path.dirname(db_path) or "."
    all_ok &= _check("DB_PATH", os.access(db_dir, os.W_OK), f"Directory '{db_dir}' must be writable")

    print()
    return all_ok


if __name__ == "__main__":
    if not validate_env():
        print("Environment validation failed. Fix the issues above and retry.")
        sys.exit(1)
    print("Environment OK.")
