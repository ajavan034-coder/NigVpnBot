import sqlite3
conn = sqlite3.connect('bot_database.db')
conn.row_factory = sqlite3.Row
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])
try:
    rows = conn.execute("SELECT id, name, panel_type, url, username FROM panels").fetchall()
    print("All panels:")
    for r in rows:
        print(f"  id={r['id']} name={r['name']} type={r['panel_type']} url={r['url']} user={r['username']}")
except Exception as e:
    print(f"panels error: {e}")
try:
    settings = conn.execute("SELECT * FROM settings WHERE key LIKE '%pasar%' OR value LIKE '%pasar%'").fetchall()
    print("PasarGuard settings:", [(s['key'], s['value'][:50]) for s in settings])
except:
    pass
conn.close()
