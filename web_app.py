import os
import secrets
import asyncio
import time
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify,
)
from dotenv import load_dotenv
import web_db
from webapp_api import webapp_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Telegram Mini Web App
app.config["BOT_TOKEN"] = os.getenv("BOT_TOKEN", "")
app.register_blueprint(webapp_bp)

ADMIN_USER = os.getenv("ADMIN_WEB_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_WEB_PASS", "changeme")

# Rate limiting for login attempts: {ip: [timestamp, ...]}
_login_attempts: dict[str, list[float]] = {}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 900  # 15 minutes


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Purge old attempts
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) < _LOGIN_MAX_ATTEMPTS


def _record_failed_login(ip: str):
    _login_attempts.setdefault(ip, []).append(time.time())


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def validate_csrf():
    token = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or token != session.get("_csrf_token"):
        return False
    return True


def _needs_setup() -> bool:
    """Check if bot needs initial setup (no BOT_TOKEN configured)."""
    token = os.getenv("BOT_TOKEN", "")
    if token:
        return False
    try:
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute("SELECT value FROM settings WHERE key = 'bot_token'").fetchone()
        conn.close()
        return not (row and row[0])
    except Exception:
        return True


@app.before_request
def setup_redirect():
    if _needs_setup() and request.endpoint not in ("setup", "static"):
        return redirect(url_for("setup"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if not _needs_setup():
        return redirect(url_for("login"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token. Please try again.", "danger")
            return redirect(url_for("setup"))

        token = request.form.get("BOT_TOKEN", "").strip()
        admin_ids = request.form.get("ADMIN_IDS", "").strip()
        panel_url = request.form.get("PANEL_URL", "").strip()
        panel_user = request.form.get("PANEL_USER", "").strip()
        panel_pass = request.form.get("PANEL_PASS", "").strip()
        sub_link_template = request.form.get("sub_link_template", "").strip()
        web_port = request.form.get("WEB_PORT", "5000").strip()
        web_user = request.form.get("ADMIN_WEB_USER", "admin").strip()
        web_pass = request.form.get("ADMIN_WEB_PASS", "").strip()

        if not token or not admin_ids or not panel_url:
            flash("Bot token, admin ID, and panel URL are required.", "danger")
            return redirect(url_for("setup"))

        # Generate secret key
        secret_key = secrets.token_hex(32)

        # Write .env file
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        env_content = (
            f"BOT_TOKEN={token}\n"
            f"ADMIN_IDS={admin_ids}\n"
            f"PANEL_URL={panel_url}\n"
            f"PANEL_USER={panel_user}\n"
            f"PANEL_PASS={panel_pass}\n"
            f"ADMIN_WEB_USER={web_user}\n"
            f"ADMIN_WEB_PASS={web_pass}\n"
            f"SECRET_KEY={secret_key}\n"
            f"WEB_PORT={web_port}\n"
            f"DB_PATH=bot_database.db\n"
        )
        with open(env_path, "w") as f:
            f.write(env_content)

        # Also save panel settings to DB
        web_db.set_setting("panel_url", panel_url)
        web_db.set_setting("panel_user", panel_user)
        web_db.set_setting("panel_pass", panel_pass)
        if sub_link_template:
            web_db.set_setting("sub_link_template", sub_link_template)

        flash("Setup complete! Bot is restarting...", "success")

        # Restart via systemd
        import subprocess
        try:
            subprocess.Popen(
                ["systemctl", "restart", "vpnbot"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

        return render_template("setup_done.html")

    return render_template("setup.html", values={})


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.before_request
def log_request():
    if request.endpoint and request.endpoint != "static":
        app.logger.info("%s %s from %s", request.method, request.path, request.remote_addr)


@app.before_request
def csrf_protect():
    if request.method == "POST" and request.endpoint not in ("login", "setup"):
        if not validate_csrf():
            flash("Invalid CSRF token. Please try again.", "danger")
            return redirect(request.referrer or url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr
        if not _check_rate_limit(ip):
            flash("Too many login attempts. Try again in 15 minutes.", "danger")
            return render_template("login.html"), 429
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            session.permanent = True
            _login_attempts.pop(ip, None)
            return redirect(url_for("dashboard"))
        _record_failed_login(ip)
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        user_count=web_db.get_user_count(),
        config_count=web_db.get_config_count(),
        revenue=web_db.get_total_revenue(),
        pending=web_db.get_pending_receipt_count(),
        symbol=web_db.get_setting("currency_symbol") or "تومان",
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        for key in request.form:
            if key.startswith("_"):
                continue
            web_db.set_setting(key, request.form[key])
        import config
        if "bot_token" in request.form and request.form["bot_token"].strip():
            new_token = request.form["bot_token"].strip()
            config.BOT_TOKEN = new_token
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            lines = []
            found = False
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("BOT_TOKEN="):
                        lines.append(f"BOT_TOKEN={new_token}\n")
                        found = True
                    else:
                        lines.append(line)
            if not found:
                lines.insert(0, f"BOT_TOKEN={new_token}\n")
            with open(env_path, "w") as f:
                f.writelines(lines)
        from api import panel_api
        panel_api.reload_config()
        flash("Settings saved successfully!", "success")
        if "bot_token" in request.form and request.form["bot_token"].strip():
            new_token = request.form["bot_token"].strip()
            import config as _cfg
            if new_token != _cfg.BOT_TOKEN:
                import subprocess
                subprocess.Popen(
                    ["systemctl", "restart", "vpnbot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                flash("Bot token changed! Bot will restart to apply.", "success")
        return redirect(url_for("settings"))
    all_settings = web_db.get_all_settings()
    qr_bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils", "qr_bg.png")
    return render_template("settings.html", settings=all_settings, qr_bg_exists=os.path.exists(qr_bg_path))


@app.route("/settings/upload-qr-bg", methods=["POST"])
@login_required
def upload_qr_bg():
    uploaded = request.files.get("qr_bg")
    if not uploaded or not uploaded.filename:
        flash("فایلی انتخاب نشد", "danger")
        return redirect(url_for("settings"))
    allowed = {"png", "jpg", "jpeg", "webp"}
    ext = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if ext not in allowed:
        flash("فرمت فایل مجاز نیست (PNG, JPG, WEBP)", "danger")
        return redirect(url_for("settings"))
    qr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils")
    os.makedirs(qr_dir, exist_ok=True)
    save_path = os.path.join(qr_dir, "qr_bg.png")
    uploaded.save(save_path)
    flash("پس‌زمینه QR با موفقیت آپلود شد!", "success")
    return redirect(url_for("settings"))


@app.route("/settings/delete-qr-bg", methods=["POST"])
@login_required
def delete_qr_bg():
    qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils", "qr_bg.png")
    if os.path.exists(qr_path):
        os.remove(qr_path)
        flash("پس‌زمینه QR حذف شد!", "success")
    return redirect(url_for("settings"))


@app.route("/qr-bg")
def serve_qr_bg():
    from flask import send_file
    qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils", "qr_bg.png")
    if os.path.exists(qr_path):
        return send_file(qr_path, mimetype="image/png")
    return "", 404


@app.route("/api/test-connection")
@login_required
def api_test_connection():
    from api import panel_api
    panel_api.reload_config()
    if not panel_api.panel_url or not panel_api.panel_user:
        return jsonify({"success": False, "message": "Panel URL or credentials not set"})
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(panel_api.login())
        loop.close()
        if result:
            return jsonify({"success": True, "message": "Connection successful!"})
        else:
            return jsonify({"success": False, "message": "Login failed - check credentials"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@app.route("/plans")
@login_required
def plans():
    return render_template(
        "plans.html",
        plans=web_db.get_all_plans(),
        symbol=web_db.get_setting("currency_symbol") or "تومان",
        plans_header=web_db.get_setting("plans_header_text") or "",
    )


@app.route("/plans/save-header", methods=["POST"])
@login_required
def plans_save_header():
    web_db.set_setting("plans_header_text", request.form.get("plans_header_text", ""))
    flash("Plans header text saved!", "success")
    return redirect(url_for("plans"))


@app.route("/plans/add", methods=["GET", "POST"])
@login_required
def plan_add():
    if request.method == "POST":
        name = request.form["name"]
        gb = int(request.form["gb"])
        days = int(request.form["days"])
        price = int(request.form["price"])
        inbound_ids = request.form.get("inbound_ids", "").strip()
        is_ultimate = "is_ultimate" in request.form
        collaborator_price = int(request.form.get("collaborator_price", 0) or 0)
        section_id = request.form.get("section_id") or None
        if section_id:
            section_id = int(section_id)
        web_db.add_plan(name, gb, days, price, inbound_ids, is_ultimate, collaborator_price)
        flash(f"Plan '{name}' added!", "success")
        return redirect(url_for("plans"))
    return render_template("plan_form.html", plan=None, sections=web_db.get_plan_sections())


@app.route("/plans/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
def plan_edit(plan_id):
    plan = web_db.get_plan(plan_id)
    if not plan:
        flash("Plan not found", "danger")
        return redirect(url_for("plans"))
    if request.method == "POST":
        section_id = request.form.get("section_id") or None
        if section_id:
            section_id = int(section_id)
        web_db.update_plan(
            plan_id,
            name=request.form["name"],
            gb=int(request.form["gb"]),
            days=int(request.form["days"]),
            price=int(request.form["price"]),
            is_active="is_active" in request.form,
            inbound_ids=request.form.get("inbound_ids", "").strip(),
            is_ultimate="is_ultimate" in request.form,
            section_id=section_id,
            collaborator_price=int(request.form.get("collaborator_price", 0) or 0),
        )
        flash(f"Plan '{request.form['name']}' updated!", "success")
        return redirect(url_for("plans"))
    return render_template("plan_form.html", plan=plan, sections=web_db.get_plan_sections())


@app.route("/plans/<int:plan_id>/delete", methods=["POST"])
@login_required
def plan_delete(plan_id):
    web_db.delete_plan(plan_id)
    flash("Plan deleted", "success")
    return redirect(url_for("plans"))


@app.route("/plan-sections")
@login_required
def plan_sections():
    return render_template("plan_sections.html", sections=web_db.get_plan_sections())


@app.route("/plan-sections/add", methods=["POST"])
@login_required
def plan_section_add():
    name = request.form["name"]
    display_order = int(request.form.get("display_order", 0))
    web_db.add_plan_section(name, display_order)
    flash(f"Section '{name}' added!", "success")
    return redirect(url_for("plan_sections"))


@app.route("/plan-sections/<int:section_id>/edit", methods=["POST"])
@login_required
def plan_section_edit(section_id):
    name = request.form["name"]
    display_order = int(request.form.get("display_order", 0))
    web_db.update_plan_section(section_id, name=name, display_order=display_order)
    flash("Section updated!", "success")
    return redirect(url_for("plan_sections"))


@app.route("/plan-sections/<int:section_id>/delete", methods=["POST"])
@login_required
def plan_section_delete(section_id):
    web_db.delete_plan_section(section_id)
    flash("Section deleted", "success")
    return redirect(url_for("plan_sections"))


@app.route("/users")
@login_required
def users():
    search = request.args.get("q", "").strip() or None
    return render_template("users.html", users=web_db.get_all_users(search), search=search)


@app.route("/users/<int:user_id>")
@login_required
def user_detail(user_id):
    user = web_db.get_user(user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for("users"))
    configs = web_db.get_user_configs(user_id)
    symbol = web_db.get_setting("currency_symbol") or "تومان"
    return render_template("user_detail.html", user=user, configs=configs, symbol=symbol)


@app.route("/users/<int:user_id>/balance", methods=["POST"])
@login_required
def user_balance(user_id):
    action = request.form["action"]
    try:
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Invalid amount", "danger")
        return redirect(url_for("user_detail", user_id=user_id))
    if action == "add":
        web_db.update_balance(user_id, amount)
        flash(f"Added {amount:,.0f}", "success")
    elif action == "remove":
        user = web_db.get_user(user_id)
        if user and user["balance"] >= amount:
            web_db.update_balance(user_id, -amount)
            flash(f"Removed {amount:,.0f}", "success")
        else:
            flash("Insufficient balance", "danger")
    return redirect(url_for("user_detail", user_id=user_id))


@app.route("/users/<int:user_id>/ban", methods=["POST"])
@login_required
def user_ban(user_id):
    user = web_db.get_user(user_id)
    if user:
        new_status = not bool(user["is_banned"])
        web_db.set_banned(user_id, new_status)
        flash("User unbanned" if not new_status else "User banned", "success")
    return redirect(url_for("user_detail", user_id=user_id))


@app.route("/receipts")
@login_required
def receipts():
    status_filter = request.args.get("status", "pending")
    if status_filter == "all":
        receipts_list = web_db.get_receipts(limit=100)
    else:
        receipts_list = web_db.get_receipts(status=status_filter, limit=100)
    symbol = web_db.get_setting("currency_symbol") or "تومان"
    return render_template("receipts.html", receipts=receipts_list, status=status_filter, symbol=symbol)


@app.route("/receipts/<int:receipt_id>/approve", methods=["POST"])
@login_required
def receipt_approve(receipt_id):
    web_db.approve_receipt(receipt_id)
    receipt = web_db.get_receipt(receipt_id)
    if receipt and receipt.get("plan_id") and receipt["plan_id"] > 0:
        import state
        if state.bot_instance and state.loop_instance:
            import asyncio
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="ساخت کانفیگ من", callback_data=f"make_config_{receipt['plan_id']}")],
            ])
            symbol = web_db.get_setting("currency_symbol") or "تومان"
            asyncio.run_coroutine_threadsafe(
                state.bot_instance.send_message(
                    chat_id=receipt["user_id"],
                    text=f"Transfer successful! ({receipt['amount']:,.0f} {symbol})\n\nClick below to get your config:",
                    reply_markup=kb,
                ),
                state.loop_instance,
            )
    flash(f"Receipt #{receipt_id} approved!", "success")
    return redirect(url_for("receipts"))


@app.route("/receipts/<int:receipt_id>/reject", methods=["POST"])
@login_required
def receipt_reject(receipt_id):
    receipt = web_db.get_receipt(receipt_id)
    web_db.reject_receipt(receipt_id)
    if receipt:
        import state
        if state.bot_instance and state.loop_instance:
            import asyncio
            symbol = web_db.get_setting("currency_symbol") or "تومان"
            asyncio.run_coroutine_threadsafe(
                state.bot_instance.send_message(
                    chat_id=receipt["user_id"],
                    text=f"Your receipt (#{receipt_id}) for {receipt['amount']:,.0f} {symbol} was rejected. Please contact admin.",
                ),
                state.loop_instance,
            )
    flash(f"Receipt #{receipt_id} rejected", "warning")
    return redirect(url_for("receipts"))


@app.route("/configs")
@login_required
def configs():
    configs_list = web_db.get_all_configs()
    symbol = web_db.get_setting("currency_symbol") or "تومان"
    return render_template("configs.html", configs=configs_list, symbol=symbol)


@app.route("/configs/<int:config_id>/delete", methods=["POST"])
@login_required
def config_delete(config_id):
    web_db.delete_config(config_id)
    flash("Config deleted", "success")
    return redirect(url_for("configs"))


@app.route("/configs/<int:config_id>/deactivate", methods=["POST"])
@login_required
def config_deactivate(config_id):
    web_db.deactivate_config(config_id)
    flash("Config deactivated", "warning")
    return redirect(url_for("configs"))


@app.route("/admins")
@login_required
def admins():
    return render_template("admins.html", admins=web_db.get_admins())


@app.route("/admins/add", methods=["POST"])
@login_required
def admin_add():
    try:
        user_id = int(request.form["user_id"])
    except (ValueError, KeyError):
        flash("Invalid user ID", "danger")
        return redirect(url_for("admins"))
    username = request.form.get("username") or None
    web_db.add_admin(user_id, username)
    flash(f"Admin {user_id} added!", "success")
    return redirect(url_for("admins"))


@app.route("/admins/<int:user_id>/remove", methods=["POST"])
@login_required
def admin_remove(user_id):
    web_db.remove_admin(user_id)
    flash(f"Admin {user_id} removed", "success")
    return redirect(url_for("admins"))


@app.route("/broadcast", methods=["GET", "POST"])
@login_required
def broadcast():
    if request.method == "POST":
        text = request.form.get("message", "").strip()
        if not text:
            flash("Message cannot be empty", "danger")
            return redirect(url_for("broadcast"))
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        users = conn.execute("SELECT id FROM users").fetchall()
        conn.close()
        count = len(users)
        flash(f"Broadcast prepared for {count} users. Use the Telegram bot /admin > Broadcast to send.", "info")
        return redirect(url_for("broadcast"))
    return render_template("broadcast.html")


@app.route("/bot-texts", methods=["GET", "POST"])
@login_required
def bot_texts():
    if request.method == "POST":
        for key in request.form:
            if key.startswith("_"):
                continue
            web_db.set_setting(key, request.form[key])
        flash("Bot texts saved successfully!", "success")
        return redirect(url_for("bot_texts"))
    from utils.texts import BOT_TEXTS
    all_settings = web_db.get_all_settings()
    texts = {}
    for key, (label, hint, variables) in BOT_TEXTS.items():
        texts[key] = {
            "label": label,
            "hint": hint,
            "variables": variables,
            "value": all_settings.get(key, ""),
        }
    return render_template("bot_texts.html", texts=texts)


@app.route("/buttons", methods=["GET", "POST"])
@login_required
def buttons():
    if request.method == "POST":
        for key in request.form:
            if key.startswith("_"):
                continue
            web_db.set_setting(key, request.form[key])
        flash("Button settings saved!", "success")
        return redirect(url_for("buttons"))
    from keyboards.user import BUTTON_CONFIGS
    all_settings = web_db.get_all_settings()
    emoji_names = [
        "wallet", "free_test", "buy_config", "my_configs", "back", "admin",
        "stats", "users", "settings", "plans", "receipts", "admins", "check", "cross",
        "card", "owner", "star", "copy", "cancel", "success", "approve", "reject",
        "ban", "unban", "plus", "minus", "list", "gear", "money", "calendar", "history",
        "menu", "package", "link", "clock", "start", "copy_number", "copy_price",
    ]
    registered = {}
    try:
        import json
        raw = all_settings.get("premium_emojis", "")
        if raw:
            registered = json.loads(raw)
    except Exception:
        pass
    styles = [
        ("", "Default"),
        ("primary", "Primary (Indigo)"),
        ("success", "Success (Green)"),
        ("danger", "Danger (Red)"),
    ]
    buttons_data = {}
    for btn_id, cfg in BUTTON_CONFIGS.items():
        buttons_data[btn_id] = {
            "label": all_settings.get(f"btn_{btn_id}", cfg["label"]),
            "emoji": all_settings.get(f"btn_emoji_{btn_id}", ""),
            "style": all_settings.get(f"btn_style_{btn_id}", cfg["default_style"]),
            "current_emoji_name": cfg["default_emoji"],
        }
    return render_template("buttons.html", buttons=buttons_data, emoji_names=emoji_names, registered=registered, styles=styles)


@app.route("/menu-layout", methods=["GET", "POST"])
@login_required
def menu_layout():
    import json
    from keyboards.user import BUTTON_CONFIGS

    BUILTIN_LABELS = {
        "wallet": "Wallet", "free_test": "Free Test", "buy_config": "Buy Config",
        "my_configs": "My Configs", "channel": "Channel", "support": "Support",
        "admin": "Admin Panel", "invite": "Referral", "collab": "Collaboration Request",
    }

    if request.method == "POST":
        layout_raw = request.form.getlist("layout[]")
        enabled = {}
        for key in request.form:
            if key.startswith("enabled_"):
                enabled[key.replace("enabled_", "")] = request.form[key] == "1"

        layout = []
        for item_id in layout_raw:
            if item_id.startswith("row_"):
                layout.append({"type": "row_break"})
            elif item_id.startswith("custom_"):
                text = request.form.get(f"custom_text_{item_id}", "")
                url = request.form.get(f"custom_url_{item_id}", "")
                style = request.form.get(f"custom_style_{item_id}", "")
                emoji_id = request.form.get(f"custom_emoji_{item_id}", "")
                if text and url:
                    layout.append({
                        "type": "custom",
                        "text": text,
                        "url": url,
                        "style": style,
                        "emoji_id": emoji_id,
                    })
            else:
                layout.append({
                    "type": "builtin",
                    "id": item_id,
                    "enabled": enabled.get(item_id, True),
                })

        web_db.set_setting("menu_layout", json.dumps(layout))
        flash("Menu layout saved!", "success")
        return redirect(url_for("menu_layout"))

    raw = web_db.get_setting("menu_layout") or "[]"
    try:
        layout = json.loads(raw)
    except Exception:
        layout = []

    buttons = []
    existing_ids = set()
    for item in layout:
        if item.get("type") == "row_break":
            buttons.append({"id": "row_break_" + str(len(buttons)), "type": "row_break"})
        elif item.get("type") == "custom":
            buttons.append({
                "id": f"custom_{len(buttons)}",
                "type": "custom",
                "text": item.get("text", ""),
                "url": item.get("url", ""),
                "style": item.get("style", ""),
                "emoji_id": item.get("emoji_id", ""),
            })
        elif item.get("type") == "builtin":
            bid = item.get("id", "")
            existing_ids.add(bid)
            buttons.append({
                "id": bid,
                "type": "builtin",
                "label": BUILTIN_LABELS.get(bid, bid),
                "enabled": item.get("enabled", True),
            })

    default_order = ["wallet", "free_test", "buy_config", "my_configs", "invite", "collab", "channel", "support", "admin"]
    for bid in default_order:
        if bid not in existing_ids:
            buttons.append({
                "id": bid,
                "type": "builtin",
                "label": BUILTIN_LABELS.get(bid, bid),
                "enabled": True,
            })

    return render_template("menu_layout.html", buttons=buttons)


# ─── Backup & Restore ───────────────────────────────────────────────
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")


def _format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backups = []
    for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if fname.endswith(".tar.gz"):
            fpath = os.path.join(BACKUP_DIR, fname)
            stat = os.stat(fpath)
            from datetime import datetime
            backups.append({
                "name": fname,
                "size": _format_size(stat.st_size),
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return backups


@app.route("/backups")
@login_required
def backups():
    return render_template("backups.html", backups=_list_backups())


@app.route("/backups/create", methods=["POST"])
@login_required
def backup_create():
    import tarfile
    import io
    import json
    from datetime import datetime

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(BACKUP_DIR, f"backup_{ts}.tar.gz")

    db_path = os.getenv("DB_PATH", "bot_database.db")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    manifest = {
        "created_at": datetime.now().isoformat(),
        "version": "1.0",
        "files": [],
    }

    with tarfile.open(archive_path, "w:gz") as tar:
        if os.path.exists(db_path):
            tar.add(db_path, arcname="bot_database.db")
            manifest["files"].append("bot_database.db")
        if os.path.exists(env_path):
            tar.add(env_path, arcname=".env")
            manifest["files"].append(".env")

        info = tarfile.TarInfo(name="backup_manifest.json")
        data = json.dumps(manifest, indent=2).encode()
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    flash(f"بکاپ با موفقیت ایجاد شد: backup_{ts}.tar.gz", "success")
    return redirect(url_for("backups"))


@app.route("/backups/<filename>/download")
@login_required
def backup_download(filename):
    import re
    if not re.match(r'^backup_\d{8}_\d{6}\.tar\.gz$', filename):
        flash("نام فایل نامعتبر است", "danger")
        return redirect(url_for("backups"))
    fpath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(fpath):
        flash("فایل بکاپ یافت نشد", "danger")
        return redirect(url_for("backups"))
    from flask import send_file
    return send_file(fpath, as_attachment=True)


@app.route("/backups/<filename>/delete", methods=["POST"])
@login_required
def backup_delete(filename):
    import re
    if not re.match(r'^backup_\d{8}_\d{6}\.tar\.gz$', filename):
        flash("نام فایل نامعتبر است", "danger")
        return redirect(url_for("backups"))
    fpath = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(fpath):
        os.remove(fpath)
        flash("بکاپ حذف شد", "success")
    return redirect(url_for("backups"))


@app.route("/backups/restore", methods=["POST"])
@login_required
def backup_restore():
    import tarfile
    import shutil
    import tempfile

    uploaded = request.files.get("backup_file")
    if not uploaded or not uploaded.filename:
        flash("فایل بکاپ را انتخاب کنید", "danger")
        return redirect(url_for("backups"))

    if not (uploaded.filename.endswith(".tar.gz") or uploaded.filename.endswith(".gz")):
        flash("فرمت فایل نامعتبر است (فایل .tar.gz)", "danger")
        return redirect(url_for("backups"))

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmp_dir, "backup.tar.gz")
        uploaded.save(tmp_path)

        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extractall(tmp_dir)

        db_path = os.getenv("DB_PATH", "bot_database.db")
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

        extracted_db = os.path.join(tmp_dir, "bot_database.db")
        extracted_env = os.path.join(tmp_dir, ".env")

        if os.path.exists(extracted_db):
            shutil.copy2(extracted_db, db_path)
        if os.path.exists(extracted_env):
            shutil.copy2(extracted_env, env_path)

        flash("بکاپ با موفقیت بازیابی شد! ربات در حال ری‌استارت...", "success")

        import subprocess
        try:
            subprocess.Popen(
                ["systemctl", "restart", "vpnbot"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    except Exception as e:
        flash(f"خطا در بازیابی بکاپ: {str(e)}", "danger")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return redirect(url_for("backups"))


if __name__ == "__main__":
    port = int(os.getenv("WEB_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
