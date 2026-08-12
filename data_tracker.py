DATA_DIR = "/root/robot/data"
BOT_USERS_FILE = f"{DATA_DIR}/bot_users.txt"
BALANCES_FILE = f"{DATA_DIR}/user_balances.txt"
PURCHASES_FILE = f"{DATA_DIR}/purchased_configs.txt"


def log_bot_user(user_id: int, username: str = "", first_name: str = ""):
    try:
        existing = set()
        try:
            with open(BOT_USERS_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split("|", 1)
                    if parts:
                        existing.add(parts[0].strip())
        except FileNotFoundError:
            pass
        uid = str(user_id)
        if uid not in existing:
            with open(BOT_USERS_FILE, "a") as f:
                f.write(f"{uid}|{username}|{first_name}\n")
    except Exception:
        pass


def update_user_balance(user_id: int, balance: float, symbol: str = "تومان"):
    try:
        lines = []
        found = False
        try:
            with open(BALANCES_FILE, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            pass
        uid = str(user_id)
        new_line = f"{uid}|{balance:,.0f}|{symbol}\n"
        new_lines = []
        for line in lines:
            if line.strip().split("|")[0] == uid:
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(new_line)
        with open(BALANCES_FILE, "w") as f:
            f.writelines(new_lines)
    except Exception:
        pass


def log_purchase(user_id: int, username: str, plan_name: str, plan_gb: int, plan_days: int, price: int, symbol: str, config_name: str = ""):
    try:
        from datetime import datetime
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(PURCHASES_FILE, "a") as f:
            f.write(f"{user_id}|{username}|{plan_name}|{plan_gb}GB|{plan_days}d|{price:,}{symbol}|{config_name}|{ts}\n")
    except Exception:
        pass
