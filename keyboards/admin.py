from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_setting
from keyboards.user import _btn


# ─── Main Admin Menu ──────────────────────────────────────────
async def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("📊 آمار", "adm_stats", "stats", btn_id="admin_stats"),
            await _btn("👥 کاربران", "adm_users", "users", btn_id="admin_users"),
            await _btn("📦 پلن‌ها", "adm_plans", "package", btn_id="admin_plans"),
        ],
        [
            await _btn("📋 رسیدها", "adm_receipts_menu", "receipts", btn_id="admin_receipts"),
            await _btn("🔑 کانفیگ‌ها", "adm_configs", "link", btn_id="admin_configs"),
            await _btn("🛡️ ادمین‌ها", "adm_admins", "owner", btn_id="admin_admins"),
        ],
        [
            await _btn("📡 پنل‌ها", "adm_panels", "gear", btn_id="admin_panels"),
            await _btn("⚙️ تنظیمات", "adm_settings", "gear", btn_id="admin_settings"),
        ],
        [
            await _btn("📢 همگانی", "adm_broadcast", "list", btn_id="admin_broadcast"),
            await _btn("🎛️ کنترل‌پنل", "adm_control", "gear", btn_id="admin_control"),
        ],
        [
            await _btn("📱 ویرایش منو", "adm_menu_editor", "gear", btn_id="admin_menu_editor"),
            await _btn("🏷️ تخفیف‌ها", "adm_discounts", "link", btn_id="admin_discounts"),
        ],
        [
            await _btn("🎁 کدهای هدیه", "adm_gift_codes", "package", btn_id="admin_gift_codes"),
            await _btn("📖 راهنماها", "adm_guides", "link", btn_id="admin_guides"),
        ],
        [await _btn("⛔ لیست سیاه", "adm_blacklist", "ban", btn_id="admin_blacklist")],
    ])


async def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")]
    ])


async def discount_codes_menu(codes: list = None) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([await _btn("➕ ایجاد کد جدید", "adm_add_discount", "link", btn_id="add_discount")])
    if codes:
        for c in codes[:10]:
            status = "🟢" if c.get("is_active") else "🔴"
            type_label = "%" if c["discount_type"] == "percent" else "تومان"
            btn_text = f"{status} {c['code']} — {c['discount_value']}{type_label} ({c['used_count']}/{c['max_uses'] or '∞'})"
            buttons.append([await _btn(btn_text, f"adm_discount_detail_{c['id']}", "link", btn_id="discount_item")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def discount_code_detail_menu(code_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_text = "🔴 غیرفعال کردن" if is_active else "🟢 فعال کردن"
    toggle_prefix = "deactivate" if is_active else "activate"
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🗑️ حذف کد", f"adm_delete_discount_{code_id}", "delete", btn_id="delete_discount", style="danger")],
        [await _btn("🔙 بازگشت", "adm_discounts", btn_id="back")],
    ])


# ─── Section 1: Stats & Reports ──────────────────────────────
async def stats_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("👥 لیست کاربران", "adm_user_list", "users"),
            await _btn("📋 رسیدهای اخیر", "adm_receipts_all", "receipts"),
        ],
        [
            await _btn("🔑 کانفیگ‌های فعال", "adm_all_configs", "link"),
            await _btn("💰 درآمد ماهانه", "adm_revenue", "money"),
        ],
        [await _btn("📥 دریافت فایل متنی", "adm_data_files", "file")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])




async def data_files_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("👥 لیست کاربران", "adm_data_users", "users")],
        [await _btn("💰 موجودی کاربران", "adm_data_balances", "money")],
        [await _btn("🔑 کانفیگ‌های خریداری شده", "adm_data_configs", "link")],
        [await _btn("📦 همه فایل‌ها", "adm_data_all", "file")],
        [await _btn("🔙 بازگشت", "adm_stats", btn_id="back")],
    ])

# ─── Section 2: User Management ──────────────────────────────
async def users_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🔍 جستجوی کاربر", "adm_search_user", "users")],
        [await _btn("📋 لیست کاربران اخیر", "adm_user_list", "list")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def user_actions(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("🔑 کانفیگ‌ها", f"adm_user_cfgs_{user_id}", "link"),
            await _btn("💰 شارژ موجودی", f"adm_add_bal_{user_id}", "money"),
        ],
        [
            await _btn("💸 کسر موجودی", f"adm_rem_bal_{user_id}", "money"),
            await _btn("🔒 مسدود/آزاد", f"adm_toggle_ban_{user_id}", "ban"),
        ],
        [await _btn("🔙 بازگشت", "adm_user_list", btn_id="back")],
    ])


async def user_list_keyboard(users: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    for u in users:
        uid = u["id"]
        uname = f"@{u.get('username', 'ندارد')}" if u.get("username") else str(uid)
        balance = u.get("balance", 0)
        buttons.append([InlineKeyboardButton(
            text=f"👤 {uname} — 💰 {balance:,.0f}",
            callback_data=f"adm_view_user_{uid}",
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm_user_page_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm_user_page_{page + 1}"))
    buttons.append(nav)
    buttons.append([await _btn("🔙 بازگشت", "adm_users", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Section 3: Plans Management ─────────────────────────────
async def plans_menu(plans: list) -> InlineKeyboardMarkup:
    symbol = await get_setting("currency_symbol") or "تومان"
    buttons = []
    for p in plans:
        collab_price = p.get("collaborator_price", 0)
        collab_text = f" | 👥 {collab_price:,}" if collab_price else ""
        name_text = f"📦 {p['name']} | {p['gb']}GB | {p['price']:,} {symbol}{collab_text}"
        buttons.append([InlineKeyboardButton(
            text=name_text,
            callback_data=f"adm_plan_detail_{p['id']}",
        )])
    buttons.append([await _btn("➕ افزودن پлин", "adm_add_plan", "plus")])
    buttons.append([await _btn("📁 مدیریت بخش‌ها", "adm_plan_sections", "gear")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def plan_actions(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("✏️ ویرایش", f"adm_edit_plan_{plan_id}", "gear"),
            await _btn("🗑️ حذف", f"adm_delete_plan_{plan_id}", "cross", "danger"),
        ],
        [await _btn("🔄 تغییر وضعیت", f"adm_toggle_plan_{plan_id}", "gear")],
        [await _btn("🔙 بازگشت", "adm_plans", btn_id="back")],
    ])


async def plan_sections_menu(sections: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in sections:
        buttons.append([InlineKeyboardButton(
            text=f"📁 {s['name']}",
            callback_data=f"adm_plan_section_{s['id']}",
        )])
    buttons.append([await _btn("➕ افزودن بخش", "adm_add_plan_section", "plus")])
    buttons.append([await _btn("🔙 بازگشت", "adm_plans", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def plan_section_actions(section_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("✏️ ویرایش", f"adm_edit_section_{section_id}", "gear"),
            await _btn("🗑️ حذف", f"adm_delete_section_{section_id}", "cross", "danger"),
        ],
        [await _btn("🔙 بازگشت", "adm_plan_sections", btn_id="back")],
    ])


# ─── Section 4: Receipts Management ──────────────────────────
async def receipts_menu(pending_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn(f"📋 در انتظار ({pending_count})", "adm_receipts_pending", "receipts")],
        [await _btn("✅ تایید شده", "adm_receipts_approved", "check")],
        [await _btn("❌ رد شده", "adm_receipts_rejected", "cross")],
        [await _btn("📋 همه", "adm_receipts_all", "list")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def receipt_list_keyboard(receipts: list, status: str) -> InlineKeyboardMarkup:
    buttons = []
    for r in receipts[:10]:
        uname = f"@{r.get('username', 'ندارد')}" if r.get("username") else str(r["user_id"])
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(r["status"], "?")
        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} #{r['id']} — {uname} — {r['amount']:,.0f}",
            callback_data=f"adm_view_receipt_{r['id']}",
        )])
    buttons.append([await _btn("🔙 بازگشت", "adm_receipts_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def receipt_actions(receipt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("✅ تایید", f"adm_approve_{receipt_id}", "approve", "success"),
            await _btn("❌ رد", f"adm_reject_{receipt_id}", "reject", "danger"),
        ],
        [await _btn("🔙 بازگشت", "adm_receipts_menu", btn_id="back")],
    ])


# ─── Section 5: Config Management ────────────────────────────
async def configs_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🔍 جستجوی کانفیگ", "adm_search_config", "link")],
        [await _btn("📋 لیست همه کانفیگ‌ها", "adm_all_configs_list", "list")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def config_list_keyboard(configs: list) -> InlineKeyboardMarkup:
    buttons = []
    for c in configs[:10]:
        status = "🟢" if c.get("is_active") else "🔴"
        expire = c.get("expire_date", "?")[:10]
        buttons.append([InlineKeyboardButton(
            text=f"{status} #{c['id']} — انقضا: {expire}",
            callback_data=f"adm_cfg_detail_{c['id']}",
        )])
    buttons.append([await _btn("🔙 بازگشت", "adm_configs", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def config_actions(config_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("🔴 غیرفعال کردن", f"adm_deactivate_cfg_{config_id}", "cross", "danger"),
            await _btn("🗑️ حذف", f"adm_delete_cfg_{config_id}", "cross", "danger"),
        ],
        [await _btn("🔙 بازگشت", "adm_configs", btn_id="back")],
    ])


# ─── Section 6: Admin Management ─────────────────────────────
async def admins_menu(admins: list) -> InlineKeyboardMarkup:
    buttons = []
    for a in admins:
        uname = f"@{a.get('username', 'ندارد')}" if a.get("username") else str(a["user_id"])
        buttons.append([InlineKeyboardButton(
            text=f"🛡️ {uname} ({a['user_id']})",
            callback_data=f"adm_admin_detail_{a['user_id']}",
        )])
    buttons.append([await _btn("➕ افزودن ادمین", "adm_add_admin", "plus", "success")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Section 7: Settings ─────────────────────────────────────
async def settings_menu() -> InlineKeyboardMarkup:
    shop_open = await get_setting("shop_open") or "1"
    shop_icon = "🟢" if shop_open == "1" else "🔴"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"─── 📝 محتوا ───", callback_data="noop")],
        [
            await _btn("📝 متن خوش‌آمدگویی", "adm_edit_welcome", "gear"),
            await _btn("🎯 ایموجی خوش‌آمد", "adm_edit_welcome_emoji", "gear"),
        ],
        [
            await _btn("📝 متن‌های ربات", "adm_edit_bot_texts", "gear"),
            await _btn("🎨 ویرایش دکمه‌ها", "adm_edit_buttons", "gear"),
        ],
        [InlineKeyboardButton(text=f"─── ⚙️ امکانات ───", callback_data="noop")],
        [
            await _btn("🧪 تست رایگان", "adm_edit_free_test", "gear"),
            await _btn("✅ تایید خودکار", "adm_edit_auto_approve", "gear"),
        ],
        [
            await _btn("🔗 عضویت اجباری", "adm_edit_force_join", "gear"),
            await _btn("👥 زیرمجموعه‌گیری", "adm_edit_invite", "link"),
        ],
        [
            await _btn("🤝 همکاری", "adm_edit_collab", "link"),
            await _btn(f"{shop_icon} فروشگاه", "adm_toggle_shop", "gear"),
        ],
        [
            await _btn("💰 کش‌بک", "adm_edit_cashback", "money"),
        ],
        [
            await _btn("📱 تایید شماره", "adm_toggle_phone_verification", "gear"),
        ],
        [InlineKeyboardButton(text=f"─── 🖥️ سرویس‌دهی ───", callback_data="noop")],
        [
            await _btn("🔍 مانیتور سرویس", "adm_toggle_service_monitor", "gear"),
        ],
        [InlineKeyboardButton(text=f"─── 💳 مالی ───", callback_data="noop")],
        [
            await _btn("💳 اطلاعات پرداخت", "adm_edit_payment", "card"),
            await _btn("💱 تنظیمات ارز", "adm_edit_currency", "money"),
        ],
        [InlineKeyboardButton(text=f"─── 🎨 نمایش ───", callback_data="noop")],
        [
            await _btn("🎭 ایموجی‌های پرمیوم", "adm_edit_premium_emojis", "star"),
            await _btn("📷 پس‌زمینه QR", "adm_qr_bg_info", "gear"),
        ],
        [
            await _btn("🔔 یادآوری انقضا", "adm_toggle_expiry_reminder", "gear"),
        ],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def payment_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("✏️ شماره کارت", "adm_edit_card_number", "card")],
        [await _btn("✏️ نام صاحب کارت", "adm_edit_card_owner", "owner")],
        [await _btn("✏️ عنوان کارت به کارت", "adm_edit_c2c_title", "gear")],
        [await _btn("✏️ راهنمای کارت به کارت", "adm_edit_c2c_instruction", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])


async def buttons_editor_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🚀 شروع", "adm_edit_btn_start", "link")],
        [await _btn("💰 کیف پول", "adm_edit_btn_wallet", "wallet")],
        [await _btn("🧪 تست رایگان", "adm_edit_btn_free_test", "gear")],
        [await _btn("🛒 خرید کانفیگ", "adm_edit_btn_buy_config", "package")],
        [await _btn("📋 سرویس‌ها", "adm_edit_btn_my_configs", "list")],
        [await _btn("🤝 درخواست همکاری", "adm_edit_btn_collab", "link")],
        [await _btn("💬 پشتیبانی", "adm_edit_btn_support", "owner")],
        [await _btn("💰 شارژ کیف پول", "adm_edit_btn_topup", "money")],
        [await _btn("📊 تاریخچه", "adm_edit_btn_tx_history", "history")],
        [await _btn("⬅️ بازگشت", "adm_edit_btn_back", "back")],
        [await _btn("🏠 بازگشت به منو", "adm_edit_btn_back_to_menu", "back")],
        [await _btn("🔙 بازگشت به تنظیمات", "adm_settings", btn_id="back")],
    ])


async def force_join_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🔄 فعال/غیرفعال", "adm_toggle_force_join", "gear")],
        [await _btn("✏️ شناسه کانال", "adm_edit_required_channel", "link")],
        [await _btn("✏️ متن عضویت اجباری", "adm_edit_force_join_text", "gear")],
        [await _btn("✏️ متن عدم عضویت", "adm_edit_force_join_fail_text", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])



async def invite_settings_menu() -> InlineKeyboardMarkup:
    enabled = await get_setting("invite_enabled") or "0"
    reward = await get_setting("invite_reward_amount") or "5000"
    symbol = await get_setting("currency_symbol") or "تومان"
    status = "فعال ✅" if enabled == "1" else "غیرفعال ❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn(f"🔄 وضعیت فعلی: {status}", "adm_toggle_invite", "gear")],
        [await _btn(f"💰 مبلغ پاداش: {reward} {symbol}", "adm_edit_invite_reward", "money")],
        [await _btn("📝 متن دعوت", "adm_edit_invite_text", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])

async def collab_settings_menu() -> InlineKeyboardMarkup:
    enabled = await get_setting("collab_enabled") or "0"
    status = "فعال ✅" if enabled == "1" else "غیرفعال ❌"
    channel = await get_setting("collab_notification_channel") or ""
    channel_display = channel if channel else "همان کانال اعلان اصلی"
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn(f"🔄 وضعیت فعلی: {status}", "adm_toggle_collab", "gear")],
        [await _btn(f"📢 کانال اعلان: {channel_display}", "adm_edit_collab_channel", "link")],
        [await _btn("📝 متن دکمه", "adm_edit_collab_btn_text", "gear")],
        [await _btn("📋 درخواست‌های در انتظار", "adm_collab_requests", "list")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])

async def panel_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("📡 مدیریت پنل‌ها", "adm_panels", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])


async def premium_emojis_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("⭐ ثبت ایموجی جدید", "adm_send_emoji_register", "star")],
        [await _btn("📋 ایموجی‌های ثبت شده", "adm_view_emojis", "list")],
        [await _btn("🗑️ حذف همه ایموجی‌ها", "adm_clear_emojis", "cross", "danger")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])


async def bot_texts_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("📝 متن خوش‌آمدگویی", "adm_text_welcome", "gear")],
        [await _btn("💰 متن کیف پول", "adm_text_wallet", "gear")],
        [await _btn("✅ متن تایید رسید", "adm_text_receipt_approved", "gear")],
        [await _btn("❌ متن رد رسید", "adm_text_receipt_rejected", "gear")],
        [await _btn("📦 متن ساخت کانفیگ", "adm_text_config_created", "gear")],
        [await _btn("🧪 متن تست رایگان", "adm_text_free_test", "gear")],
        [await _btn("📢 متن کاربر جدید", "adm_text_new_user", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])


# ─── Section 8: Control Panel ────────────────────────────────
async def control_panel_menu() -> InlineKeyboardMarkup:
    from database import get_setting
    mode = await get_setting("operating_mode") or "NORMAL"
    mode_labels = {"NORMAL": "🟢 عادی", "SALES_PAUSED": "🟡 فروش متوقف", "MAINTENANCE": "🔴 تعمیرات"}
    mode_text = mode_labels.get(mode, mode)
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn(f"⚡ حالت: {mode_text}", "adm_toggle_mode", "gear")],
        [await _btn("🧪 تست اتصال پنل", "adm_test_connection_ctrl", "check", "success")],
        [await _btn("🔍 بررسی دستی سرویس‌ها", "cb_force_check_services", "check", "primary")],
        [await _btn("🔄 ری‌استارت ربات", "adm_restart_bot", "gear", "danger")],
        [await _btn("🖥️ وضعیت سرور", "adm_server_status", "gear")],
        [await _btn("💾 ایجاد بکاپ", "adm_create_backup", "gear", "primary")],
        [await _btn("📥 بکاپ‌های موجود", "adm_backups_list", "list")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def backup_list_keyboard(backups: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in backups[:10]:
        buttons.append([InlineKeyboardButton(
            text=f"💾 {b['name']} ({b['size']})",
            callback_data=f"adm_backup_{b['name']}",
        )])
    buttons.append([await _btn("🔙 بازگشت", "adm_control", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Section 9: Broadcast ────────────────────────────────────
async def broadcast_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


# ─── Section 10: Menu Editor ─────────────────────────────────
async def broadcast_destination_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("👥 ارسال به کاربران", "broadcast_dest_users", "users")],
        [await _btn("📢 ارسال به کانال", "broadcast_dest_channel", "link")],
        [await _btn("🔄 ارسال به هر دو", "broadcast_dest_both", "list")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])


async def broadcast_button_keyboard() -> InlineKeyboardMarkup:
    from keyboards.user import _btn as user_btn
    return InlineKeyboardMarkup(inline_keyboard=[
        [await user_btn("❌ بدون دکمه", "broadcast_send_none", "cross", btn_id="cancel")],
        [await user_btn(await get_setting("btn_buy_config") or "🛒 خرید کانفیگ", "broadcast_send_buy_config", "package", btn_id="buy_config")],
        [await user_btn(await get_setting("btn_wallet") or "💰 کیف پول", "broadcast_send_wallet", "wallet", btn_id="wallet")],
        [await user_btn("🧪 تست رایگان", "broadcast_send_free_test", "free_test", btn_id="free_test")],
        [await user_btn(await get_setting("btn_channel") or "📢 کانال", "broadcast_send_channel", "link", btn_id="channel")],
        [await user_btn(await get_setting("btn_support") or "💬 پشتیبانی", "broadcast_send_support", "owner", btn_id="support")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])



async def broadcast_pin_keyboard() -> InlineKeyboardMarkup:
    from keyboards.user import _btn as user_btn
    return InlineKeyboardMarkup(inline_keyboard=[
        [await user_btn("📌 پین شود", "broadcast_pin_yes", "pin", btn_id="pin")],
        [await user_btn("🚫 بدون پین", "broadcast_pin_no", "cross", btn_id="nopin")],
        [await _btn("🔙 بازگشت", "adm_menu", btn_id="back")],
    ])

async def menu_editor_menu(layout_summary: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, item in enumerate(layout_summary):
        icon = "✅" if item.get("enabled", True) else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {i+1}. {item.get('label', item.get('id', '?'))}",
            callback_data=f"adm_menu_toggle_{i}",
        )])
    buttons.append([await _btn("🔀 افزودن ردیف", "adm_menu_add_row", "gear")])
    buttons.append([await _btn("➕ دکمه سفارشی", "adm_menu_add_custom", "plus")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def collab_requests_list(requests: list) -> InlineKeyboardMarkup:
    buttons = []
    for r in requests[:10]:
        uname = f"@{r.get('username', 'ندارد')}" if r.get("username") else str(r["user_id"])
        buttons.append([InlineKeyboardButton(
            text=f"🤝 #{r['id']} — {uname}",
            callback_data=f"adm_collab_detail_{r['id']}",
        )])
    buttons.append([await _btn("🔙 بازگشت", "adm_edit_collab", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def collab_request_actions(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("✅ تایید", f"collab_approve_{request_id}", "approve", "success"),
            await _btn("❌ رد", f"collab_reject_{request_id}", "reject", "danger"),
        ],
        [await _btn("💬 پاسخ به کاربر", f"collab_reply_{request_id}", "reply", "primary")],
        [await _btn("🔙 بازگشت", "adm_collab_requests", btn_id="back")],
    ])


async def trial_management_menu() -> InlineKeyboardMarkup:
    from database import get_setting
    enabled = await get_setting("free_test_enabled") or "1"
    mb = await get_setting("free_test_mb") or "102400"
    days = await get_setting("free_test_days") or "1"
    inbound_ids = await get_setting("free_test_inbound_ids") or ""
    status = "فعال ✅" if enabled == "1" else "غیرفعال ❌"
    inbound_display = inbound_ids if inbound_ids else "پیش‌فرض پنل"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔄 وضعیت: {status}", callback_data="adm_trial_toggle")],
        [await _btn(f"📊 حجم: {mb} MB", "adm_trial_edit_mb", "gear")],
        [await _btn(f"📅 مدت: {days} روز", "adm_trial_edit_days", "gear")],
        [await _btn(f"🔗 ردیف‌ها: {inbound_display}", "adm_trial_edit_inbounds", "gear")],
        [await _btn("👥 لیست کاربران تست", "adm_trial_users", "users")],
        [await _btn("🔄 ریست همه کاربران", "adm_trial_reset_all", "gear")],
        [await _btn("🔙 بازگشت", "adm_settings", btn_id="back")],
    ])


async def blacklist_keyboard(users: list) -> InlineKeyboardMarkup:
    buttons = []
    for u in users:
        uid = u["user_id"]
        uname = f"@{u.get('username', 'ندارد')}" if u.get("username") else str(uid)
        reason = u.get("reason", "")
        reason_short = f" — {reason[:20]}" if reason else ""
        buttons.append([InlineKeyboardButton(
            text=f"👤 {uname} ({uid}){reason_short}",
            callback_data=f"adm_blacklist_detail_{uid}",
        )])
    buttons.append([await _btn("➕ مسدود کردن کاربر", "adm_blacklist_add", "plus", "danger")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Gift Codes Management ───────────────────────────────────
async def gift_codes_menu(codes: list = None) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([await _btn("➕ ایجاد کد جدید", "adm_add_gift_code", "plus", btn_id="add_gift_code")])
    if codes:
        for c in codes[:10]:
            status = "🟢" if c.get("active") else "🔴"
            btn_text = f"{status} {c['code']} — {c['amount']:,.0f} ({c['uses']}/{c['max_uses'] or '∞'})"
            buttons.append([await _btn(btn_text, f"adm_gift_detail_{c['id']}", "link", btn_id="gift_item")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def gift_code_detail_menu(code_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_text = "🔴 غیرفعال کردن" if is_active else "🟢 فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("🗑️ حذف کد", f"adm_delete_gift_code_{code_id}", "delete", btn_id="delete_gift_code", style="danger")],
        [await _btn("🔙 بازگشت", "adm_gift_codes", btn_id="back")],
    ])


# ─── Guides Management ───────────────────────────────────────
async def guides_menu() -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([await _btn("➕ افزودن راهنما", "adm_add_guide", "plus", btn_id="add_guide")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def guide_platforms_menu() -> InlineKeyboardMarkup:
    platforms = [
        ("Android", "android"),
        ("iOS", "ios"),
        ("Windows", "windows"),
        ("macOS", "macos"),
        ("Linux", "linux"),
        ("Android TV", "android_tv"),
    ]
    buttons = []
    for label, slug in platforms:
        buttons.append([await _btn(label, f"adm_guide_platform_{slug}", "link", btn_id="guide_platform")])
    buttons.append([await _btn("🔙 بازگشت", "adm_menu", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Confirm Dialogs ─────────────────────────────────────────
async def confirm_action(callback_data: str, text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            await _btn("✅ بله", callback_data, "check", "success"),
            await _btn("❌ خیر", "adm_menu", "cross", "danger"),
        ],
    ])
