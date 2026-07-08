import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "bot_database.db")

def _get_bot_token():
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute("SELECT value FROM settings WHERE key = 'bot_token'").fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return os.getenv("BOT_TOKEN", "")

BOT_TOKEN = _get_bot_token()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

PANEL_URL = os.getenv("PANEL_URL", "")
PANEL_USER = os.getenv("PANEL_USER", "")
PANEL_PASS = os.getenv("PANEL_PASS", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
