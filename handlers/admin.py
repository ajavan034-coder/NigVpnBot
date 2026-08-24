import logging
import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    is_admin, get_setting, set_setting,
    get_user, get_user_count, search_users, get_all_users,
    update_balance, set_banned,
    get_config_count, get_all_plans, get_plan, add_plan, update_plan, delete_plan,
    get_pending_receipts, get_receipt, approve_receipt, reject_receipt,
    get_user_configs, get_all_plans as _get_all_plans,
    add_admin, remove_admin, get_admins, get_user_count_by_period,
    get_total_revenue, get_plan_sections, get_plan_section,
    add_plan_section, update_plan_section, delete_plan_section,
    add_discount_code, get_discount_code, get_discount_code_by_id,
    use_discount_code, delete_discount_code, get_all_discount_codes,
    reset_free_test, get_free_test_users, reset_all_free_tests,
    add_collab_request, get_collab_request, get_pending_collab_requests,
    update_collab_request, set_user_collaborator,
    is_blacklisted, add_to_blacklist, remove_from_blacklist, get_blacklisted_users,
    get_all_gift_codes, get_gift_code_by_id, add_gift_code, delete_gift_code, toggle_gift_code,
    get_all_guides, delete_guide_item, add_guide_item,
    add_tutorial, get_tutorials, get_tutorial, update_tutorial, delete_tutorial, toggle_tutorial,
    add_tutorial_item, get_tutorial_items, get_tutorial_item, update_tutorial_item, delete_tutorial_item,
    get_support_user,
)
from api import panel_api
from keyboards.admin import (
    admin_menu, back_to_admin, stats_menu,
    users_menu, user_actions, user_list_keyboard,
    plans_menu, plan_actions, plan_sections_menu, plan_section_actions,
    receipts_menu, receipt_list_keyboard, receipt_actions,
    configs_menu, config_list_keyboard, config_actions,
    admins_menu, settings_menu, payment_settings_menu,
    buttons_editor_menu, force_join_settings_menu, invite_settings_menu,
    collab_settings_menu, collab_requests_list, collab_request_actions,
    premium_emojis_menu, bot_texts_menu,
    control_panel_menu, backup_list_keyboard,
    broadcast_menu, broadcast_destination_keyboard, broadcast_button_keyboard, broadcast_pin_keyboard, menu_editor_menu, confirm_action,
    discount_codes_menu, discount_code_detail_menu,
    trial_management_menu, blacklist_keyboard,
    gift_codes_menu, gift_code_detail_menu, guides_menu, guide_platforms_menu,
    tutorials_menu, tutorial_detail_menu, tutorial_item_detail_menu,
)
from keyboards.user import _btn

logger = logging.getLogger(__name__)
router = Router()

ITEMS_PER_PAGE = 5


# ─── FSM States ──────────────────────────────────────────────
class AdminState(StatesGroup):
    search_user = State()
    search_config = State()
    add_plan_name = State()
    add_plan_gb = State()
    add_plan_days = State()
    add_plan_price = State()
    add_plan_panel = State()
    add_plan_ip_limit = State()
    add_plan_collab_price = State()
    add_plan_service_type = State()
    edit_plan_field = State()
    add_plan_section_name = State()
    edit_plan_section_name = State()
    add_admin_id = State()
    edit_welcome = State()
    edit_welcome_emoji = State()
    edit_button_name = State()
    edit_currency = State()
    edit_card_number = State()
    edit_card_owner = State()
    edit_c2c_title = State()
    edit_c2c_instruction = State()
    edit_free_test_mb = State()
    edit_trial_days = State()
    edit_trial_inbounds = State()
    edit_auto_approve = State()
    edit_required_channel = State()
    edit_force_join_text = State()
    edit_force_join_fail_text = State()
    add_balance = State()
    remove_balance = State()
    broadcast = State()
    broadcast_destination = State()
    broadcast_text = State()
    broadcast_button = State()
    broadcast_pin = State()
    waiting_emoji_name = State()
    waiting_emoji_id = State()
    edit_bot_text_key = State()
    edit_invite_reward = State()
    edit_invite_text = State()
    add_discount_code = State()
    add_discount_type = State()
    add_discount_value = State()
    add_discount_max = State()
    add_discount_expiry = State()
    add_discount_plan = State()
    edit_collab_channel = State()
    edit_collab_btn_text = State()
    collab_reject_reason = State()
    collab_reply_text = State()
    edit_invite_reward_type = State()
    edit_invite_commission = State()
    edit_shop_message = State()
    blacklist_add_id = State()
    blacklist_add_reason = State()
    gift_code_code = State()
    gift_code_amount = State()
    gift_code_max_uses = State()
    guide_platform = State()
    guide_body = State()
    tutorial_title = State()
    tutorial_edit_title = State()
    tutitem_title = State()
    tutitem_content = State()
    tutitem_mediatitle = State()
    tutitem_edit = State()
    guide_media = State()
    edit_cashback_percent = State()


# ─── Entry Point ─────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🛡️ <b>پنل مدیریت ربات</b>", parse_mode="HTML", reply_markup=await admin_menu())


@router.callback_query(F.data == "adm_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    try:
        await callback.message.edit_text("🛡️ <b>پنل مدیریت ربات</b>", parse_mode="HTML", reply_markup=await admin_menu())
    except Exception:
        await callback.message.answer("🛡️ <b>پنل مدیریت ربات</b>", parse_mode="HTML", reply_markup=await admin_menu())


# ═══════════════════════════════════════════════════════════════
# SECTION 1: Stats & Reports
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_stats")
async def cb_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    user_count = await get_user_count()
    config_count = await get_config_count()
    revenue = await get_total_revenue()
    pending = len(await get_pending_receipts())
    today = await get_user_count_by_period(1)
    week = await get_user_count_by_period(7)
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📊 <b>آمار و گزارش‌ها</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👥 کل کاربران: <b>{user_count}</b>\n"
        f"  🔑 کانفیگ‌های فعال: <b>{config_count}</b>\n"
        f"  💰 درآمد کل: <b>{revenue:,.0f} {symbol}</b>\n"
        f"  📋 رسیدهای در انتظار: <b>{pending}</b>\n"
        f"  📅 امروز: <b>{today}</b> کاربر جدید\n"
        f"  📅 ۷ روز اخیر: <b>{week}</b> کاربر"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await stats_menu())



# ─── Data Files ──────────────────────────────────────────────
DATA_DIR = "/root/robot/data"

DATA_FILE_MAP = {
    "adm_data_users": ("bot_users.txt", "👥 لیست کاربران ربات"),
    "adm_data_balances": ("user_balances.txt", "💰 موجودی کاربران"),
    "adm_data_configs": ("purchased_configs.txt", "🔑 کانفیگ‌های خریداری شده"),
    "adm_data_all": (None, "📦 همه فایل‌ها"),
}


@router.callback_query(F.data == "adm_data_files")
async def cb_data_files(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from keyboards.admin import data_files_menu
    await callback.message.edit_text(
        "📥 <b>انتخاب فایل متنی:</b>",
        parse_mode="HTML",
        reply_markup=await data_files_menu(),
    )


@router.callback_query(F.data.startswith("adm_data_"))
async def cb_send_data_file(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from aiogram.types import FSInputFile
    from datetime import datetime

    data_key = callback.data
    if data_key == "adm_data_files":
        return

    if data_key == "adm_data_all":
        for fname, _label in DATA_FILE_MAP.values():
            if fname is None:
                continue
            path = os.path.join(DATA_DIR, fname)
            if os.path.exists(path):
                await callback.message.answer_document(
                    FSInputFile(path),
                    caption=f"📄 {fname}",
                )
        await callback.answer("✅ همه فایل‌ها ارسال شد!", show_alert=True)
    elif data_key in DATA_FILE_MAP:
        fname, label = DATA_FILE_MAP[data_key]
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            await callback.message.answer_document(
                FSInputFile(path),
                caption=f"📄 {label} ({fname})",
            )
            await callback.answer("✅ فایل ارسال شد!", show_alert=True)
        else:
            await callback.answer("❌ فایل یافت نشد!", show_alert=True)

@router.callback_query(F.data == "adm_all_configs")
async def cb_all_configs(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from database import get_db
    db = await get_db()
    cursor = await db.execute(
        "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id "
        "WHERE c.is_active = 1 ORDER BY c.created_at DESC LIMIT 15"
    )
    configs = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    if not configs:
        await callback.message.edit_text("🔑 <b>کانفیگ‌های فعال</b>\n\nهیچ کانفیگ فعالی وجود ندارد.", parse_mode="HTML", reply_markup=await back_to_admin())
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    text = "━━━━━━━━━━━━━━━━━━━━━━\n  🔑 <b>کانفیگ‌های فعال</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in configs:
        uname = f"@{c.get('username', 'ندارد')}" if c.get("username") else str(c["user_id"])
        text += f"  🟢 #{c['id']} — {uname} — انقضا: {c['expire_date'][:10]}\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data == "adm_revenue")
async def cb_revenue(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from database import get_db
    symbol = await get_setting("currency_symbol") or "تومان"
    db = await get_db()
    cursor = await db.execute("SELECT SUM(amount) as total FROM receipts WHERE status = 'approved'")
    total = (await cursor.fetchone())["total"] or 0
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM receipts WHERE status = 'approved'")
    count = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM receipts WHERE status = 'pending'")
    pending = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM receipts WHERE status = 'rejected'")
    rejected = (await cursor.fetchone())["cnt"]
    await db.close()
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰 <b>گزارش درآمد</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  💰 درآمد کل: <b>{total:,.0f} {symbol}</b>\n"
        f"  ✅ تعداد تایید شده: <b>{count}</b>\n"
        f"  ⏳ در انتظار: <b>{pending}</b>\n"
        f"  ❌ رد شده: <b>{rejected}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await stats_menu())


# ═══════════════════════════════════════════════════════════════
# SECTION 2: User Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_users")
async def cb_users(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "  👥 <b>مدیریت کاربران</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "  🔍 آیدی عددی یا نام کاربری را ارسال کنید\n"
        "  یا از دکمه‌های زیر استفاده کنید:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await users_menu())


@router.callback_query(F.data == "adm_user_list")
async def cb_user_list(callback: CallbackQuery):
    await _show_user_page(callback, 1)


@router.callback_query(F.data.startswith("adm_user_page_"))
async def cb_user_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    await _show_user_page(callback, page)


async def _show_user_page(callback: CallbackQuery, page: int):
    if not await is_admin(callback.from_user.id):
        return
    users = await get_all_users()
    total = len(users)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    page_users = users[start:start + ITEMS_PER_PAGE]
    text = f"━━━━━━━━━━━━━━━━━━━━━━\n  👥 <b>لیست کاربران</b> ({page}/{total_pages})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, u in enumerate(page_users, start + 1):
        uname = f"@{u.get('username', 'ندارد')}" if u.get("username") else str(u["id"])
        text += f"  {i}. {uname} — 💰 {u.get('balance', 0):,.0f}\n"
    kb = await user_list_keyboard(page_users, page, total_pages)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "adm_search_user")
async def cb_search_user(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.search_user)
    await callback.message.edit_text(
        "🔍 <b>جستجوی کاربر</b>\n\nآیدی عددی یا نام کاربری را ارسال کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.search_user)
async def process_search_user(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    users = await search_users(message.text.strip())
    if not users:
        await message.answer("❌ کاربری یافت نشد.", reply_markup=await back_to_admin())
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    text = f"🔍 <b>نتایج جستجو</b> ({len(users)} نتیجه)\n\n"
    for u in users[:10]:
        uname = f"@{u.get('username', 'ندارد')}" if u.get("username") else str(u["id"])
        text += f"  👤 {uname} (ID: {u['id']}) — 💰 {u.get('balance', 0):,.0f}\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for u in users[:10]:
        uname = f"@{u.get('username', 'ندارد')}" if u.get("username") else str(u["id"])
        buttons.append([InlineKeyboardButton(text=f"👤 {uname}", callback_data=f"adm_view_user_{u['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_users")])
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("adm_view_user_"))
async def cb_view_user(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    user = await get_user(user_id)
    if not user:
        await callback.answer("❌ کاربر یافت نشد!", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    configs = await get_user_configs(user_id)
    active = len([c for c in configs if c["is_active"]])
    banned = "🔒 بله" if user["is_banned"] else "🔓 خیر"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  👤 <b>اطلاعات کاربر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  🔢 آیدی: <code>{user['id']}</code>\n"
        f"  👤 نام کاربری: @{user.get('username', 'ندارد')}\n"
        f"  📛 نام: {user.get('first_name', 'ندارد')}\n"
        f"  💰 موجودی: <b>{user.get('balance', 0):,.0f} {symbol}</b>\n"
        f"  📅 تاریخ عضویت: {user.get('created_at', '?')[:10]}\n"
        f"  🔑 کانفیگ‌ها: {active} فعال\n"
        f"  {banned}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await user_actions(user_id))


@router.callback_query(F.data.startswith("adm_toggle_ban_"))
async def cb_toggle_ban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    user = await get_user(user_id)
    if not user:
        await callback.answer("❌ کاربر یافت نشد!", show_alert=True)
        return
    new_status = not bool(user["is_banned"])
    await set_banned(user_id, new_status)
    status = "مسدود شد 🔒" if new_status else "از مسدودی خارج شد 🔓"
    await callback.answer(f"کاربر {status}", show_alert=True)
    await cb_view_user(callback)


@router.callback_query(F.data.startswith("adm_add_bal_"))
async def cb_add_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(bal_user_id=user_id)
    await state.set_state(AdminState.add_balance)
    symbol = await get_setting("currency_symbol") or "تومان"
    await callback.message.edit_text(
        f"💰 <b>شارژ موجودی</b>\n\nمبلغ را به {symbol} وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.add_balance)
async def process_add_balance(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    data = await state.get_data()
    user_id = data.get("bal_user_id")
    await update_balance(user_id, amount)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    new_balance = user["balance"] if user else 0
    await message.answer(
        f"✅ <b>{amount:,.0f} {symbol}</b> به کاربر <code>{user_id}</code> اضافه شد.\n"
        f"موجودی جدید: <b>{new_balance:,.0f} {symbol}</b>",
        parse_mode="HTML", reply_markup=await user_actions(user_id)
    )


@router.callback_query(F.data.startswith("adm_rem_bal_"))
async def cb_remove_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(bal_user_id=user_id)
    await state.set_state(AdminState.remove_balance)
    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    balance = user["balance"] if user else 0
    await callback.message.edit_text(
        f"💸 <b>کسر موجودی</b>\n\nموجودی فعلی: <b>{balance:,.0f} {symbol}</b>\n\nمبلغ کسر را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.remove_balance)
async def process_remove_balance(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    data = await state.get_data()
    user_id = data.get("bal_user_id")
    user = await get_user(user_id)
    if user and user["balance"] < amount:
        await message.answer(f"❌ موجودی کافی نیست. موجودی فعلی: {user['balance']:,.0f}")
        return
    await update_balance(user_id, -amount)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    new_balance = user["balance"] if user else 0
    await message.answer(
        f"✅ <b>{amount:,.0f} {symbol}</b> از کاربر <code>{user_id}</code> کسر شد.\n"
        f"موجودی جدید: <b>{new_balance:,.0f} {symbol}</b>",
        parse_mode="HTML", reply_markup=await user_actions(user_id)
    )


@router.callback_query(F.data.startswith("adm_user_cfgs_"))
async def cb_user_configs(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    configs = await get_user_configs(user_id)
    user = await get_user(user_id)
    uname = f"@{user.get('username', 'ندارد')}" if user else str(user_id)
    if not configs:
        await callback.message.edit_text(f"🔑 <b>کانفیگ‌های {uname}</b>\n\nهیچ کانفیگی یافت نشد.", parse_mode="HTML", reply_markup=await user_actions(user_id))
        return
    text = f"━━━━━━━━━━━━━━━━━━━━━━\n  🔑 <b>کانفیگ‌های {uname}</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for c in configs[:10]:
        icon = "🟢" if c["is_active"] else "🔴"
        text += f"  {icon} #{c['id']} — {c['email'][:30]} — انقضا: {c['expire_date'][:10]}\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for c in configs[:10]:
        icon = "🟢" if c["is_active"] else "🔴"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} #{c['id']} — {c['expire_date'][:10]}",
            callback_data=f"adm_cfg_detail_{c['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_view_user_{user_id}")])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


# ═══════════════════════════════════════════════════════════════
# SECTION 3: Plans Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_plans")
async def cb_plans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    plans = await get_all_plans()
    if not plans:
        await callback.message.edit_text("📦 <b>مدیریت پلن‌ها</b>\n\nهیچ پلنی وجود ندارد.", parse_mode="HTML", reply_markup=await back_to_admin())
        return
    await callback.message.edit_text("📦 <b>مدیریت پلن‌ها</b>", parse_mode="HTML", reply_markup=await plans_menu(plans))


@router.callback_query(F.data.startswith("adm_plan_detail_"))
async def cb_plan_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ پلن یافت نشد!", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    status = "✅ فعال" if plan["is_active"] else "❌ غیرفعال"
    inbound_ids = plan.get("inbound_ids", "")
    ib_text = inbound_ids if inbound_ids else "پیش‌فرض"
    ip_limit = plan.get("ip_limit", 0)
    ip_text = f"{ip_limit}" if ip_limit > 0 else "بدون محدودیت"
    collab_price = plan.get("collaborator_price", 0)
    collab_text = f"{collab_price:,} {symbol}" if collab_price > 0 else "غیرفعال"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📦 <b>{plan['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📊 حجم: <b>{plan['gb']} GB</b>\n"
        f"  📅 مدت: <b>{plan['days']} روز</b>\n"
        f"  💰 قیمت: <b>{plan['price']:,} {symbol}</b>\n"
        f"  👥 قیمت همکاری: <b>{collab_text}</b>\n"
        f"  📡 اینباندها: <b>{ib_text}</b>\n"
        f"  🔒 محدودیت IP: <b>{ip_text}</b>\n"
        f"  📌 وضعیت: <b>{status}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await plan_actions(plan_id))


@router.callback_query(F.data == "adm_add_plan")
async def cb_add_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_plan_name)
    await callback.message.edit_text("📦 <b>افزودن پلن جدید</b>\n\nنام پلن را وارد کنید (مثال: ۱ ماهه):", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.add_plan_name)
async def process_plan_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.update_data(plan_name=message.text)
    await state.set_state(AdminState.add_plan_gb)
    await message.answer("📊 حجم را به گیگابایت وارد کنید (مثال: 50):")


@router.message(AdminState.add_plan_gb)
async def process_plan_gb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        gb = int(message.text.strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(plan_gb=gb)
    await state.set_state(AdminState.add_plan_days)
    await message.answer("📅 مدت را به روز وارد کنید (مثال: 30):")


@router.message(AdminState.add_plan_days)
async def process_plan_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(plan_days=days)
    symbol = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.add_plan_price)
    await message.answer(f"💰 قیمت را به {symbol} وارد کنید (مثال: 150000):")


@router.message(AdminState.add_plan_price)
async def process_plan_price(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ قیمت نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(plan_price=price)
    # Show panel selection
    from api import panel_manager
    await panel_manager.load_all()
    panels = list(panel_manager._instances.values())
    if not panels:
        # No panels configured, use legacy panel_api
        from api import panel_api
        panel_api.reload_config()
        await state.update_data(plan_panel_id=None)
        try:
            loop = asyncio.new_event_loop()
            login_ok = loop.run_until_complete(panel_api.login())
            if login_ok:
                inbounds = loop.run_until_complete(panel_api.get_inbounds())
            else:
                inbounds = None
            loop.close()
        except Exception:
            inbounds = None
        if not inbounds:
            await state.update_data(plan_inbound_ids="")
            await state.set_state(AdminState.add_plan_ip_limit)
            await message.answer(
                "⚠️ پنلی متصل نیست. محدودیت IP را وارد کنید\n(۰ = بدون محدودیت):",
            )
            return
        await state.update_data(plan_inbounds_available=[{"id": ib["id"], "tag": ib.get("tag", "?"), "proto": ib.get("protocol", "?")} for ib in inbounds])
        await state.update_data(plan_selected_inbounds=[])
        await _show_inbound_selection(message, state)
        return
    if len(panels) == 1:
        # Only one panel, use it directly
        p = panels[0]
        await state.update_data(plan_panel_id=p.panel_id)
        try:
            loop = asyncio.new_event_loop()
            login_ok = loop.run_until_complete(p.login())
            if login_ok:
                inbounds = loop.run_until_complete(p.get_inbounds())
            else:
                inbounds = None
            loop.close()
        except Exception:
            inbounds = None
        if not inbounds:
            await state.update_data(plan_inbound_ids="")
            await state.set_state(AdminState.add_plan_ip_limit)
            await message.answer(
                "⚠️ اینباندی یافت نشد. محدودیت IP را وارد کنید\n(۰ = بدون محدودیت):",
            )
            return
        await state.update_data(plan_inbounds_available=[{"id": ib["id"], "tag": ib.get("tag", "?"), "proto": ib.get("protocol", "?")} for ib in inbounds])
        await state.update_data(plan_selected_inbounds=[])
        await _show_inbound_selection(message, state)
        return
    # Multiple panels, show selection
    await state.set_state(AdminState.add_plan_panel)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for p in panels:
        buttons.append([InlineKeyboardButton(
            text=f"📡 {p.panel_url[:40]}",
            callback_data=f"adm_select_plan_panel_{p.panel_id}",
        )])
    buttons.append([InlineKeyboardButton(text="⏭️ پنل پیش‌فرض", callback_data="adm_select_plan_panel_default")])
    buttons.append([InlineKeyboardButton(text="❌ لغو", callback_data="adm_plans")])
    await message.answer(
        "📡 <b>انتخاب پنل</b>\n\nپنل مورد نظر برای این پلن را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm_svc_"))
async def cb_select_service_type(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    svc_type = callback.data.split("_")[-1]  # v2ray or wireguard
    await state.update_data(plan_service_type=svc_type)
    
    if svc_type == "wireguard":
        # Wireguard doesn't need inbound selection, go to IP limit
        await state.update_data(plan_inbound_ids="")
        await state.set_state(AdminState.add_plan_ip_limit)
        await callback.message.edit_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "  🔒 <b>محدودیت IP</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "  حداکثر تعداد IP همزمان:\n"
            "  (۰ = بدون محدودیت)\n",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="0 — بدون محدودیت", callback_data="adm_ip_0"),
                    InlineKeyboardButton(text="1", callback_data="adm_ip_1"),
                ],
                [
                    InlineKeyboardButton(text="2", callback_data="adm_ip_2"),
                    InlineKeyboardButton(text="3", callback_data="adm_ip_3"),
                ],
                [
                    InlineKeyboardButton(text="5", callback_data="adm_ip_5"),
                    InlineKeyboardButton(text="10", callback_data="adm_ip_10"),
                ],
                [InlineKeyboardButton(text="✏️ عدد دیگر", callback_data="adm_ip_custom")],
            ])
        )
        await callback.answer()
        return
    
    # V2Ray: show panel selection as before
    await callback.answer()
    # Continue with existing panel selection flow
    from api import panel_manager
    await panel_manager.load_all()
    panels_list = list(panel_manager._instances.values())
    if not panels_list:
        from api import panel_api
        panel_api.reload_config()
        await state.update_data(plan_panel_id=None)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            login_ok = loop.run_until_complete(panel_api.login())
            if login_ok:
                inbounds = loop.run_until_complete(panel_api.get_inbounds())
            else:
                inbounds = None
            loop.close()
        except Exception:
            inbounds = None
        if not inbounds:
            await state.update_data(plan_inbound_ids="")
            await state.set_state(AdminState.add_plan_ip_limit)
            await callback.message.edit_text(
                "⚠️ پنلی متصل نیست. محدودیت IP را وارد کنید\n(۰ = بدون محدودیت):",
            )
            return
        await state.update_data(plan_inbounds_available=[{"id": ib["id"], "tag": ib.get("tag", "?"), "proto": ib.get("protocol", "?")} for ib in inbounds])
        await state.update_data(plan_selected_inbounds=[])
        await _show_inbound_selection(callback.message, state)
        return
    if len(panels_list) == 1:
        p = panels_list[0]
        await state.update_data(plan_panel_id=p.panel_id)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            login_ok = loop.run_until_complete(p.login())
            if login_ok:
                inbounds = loop.run_until_complete(p.get_inbounds())
            else:
                inbounds = None
            loop.close()
        except Exception:
            inbounds = None
        if not inbounds:
            await state.update_data(plan_inbound_ids="")
            await state.set_state(AdminState.add_plan_ip_limit)
            await callback.message.edit_text(
                "⚠️ اینباندی یافت نشد. محدودیت IP را وارد کنید\n(۰ = بدون محدودیت):",
            )
            return
        await state.update_data(plan_inbounds_available=[{"id": ib["id"], "tag": ib.get("tag", "?"), "proto": ib.get("protocol", "?")} for ib in inbounds])
        await state.update_data(plan_selected_inbounds=[])
        await _show_inbound_selection(callback.message, state)
        return
    # Multiple panels
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for p in panels_list:
        buttons.append([InlineKeyboardButton(
            text=f"📡 {p.panel_url[:40]}",
            callback_data=f"adm_select_plan_panel_{p.panel_id}",
        )])
    buttons.append([InlineKeyboardButton(text="⏭️ پنل پیش‌فرض", callback_data="adm_select_plan_panel_default")])
    buttons.append([InlineKeyboardButton(text="❌ لغو", callback_data="adm_plans")])
    await callback.message.edit_text(
        "📡 <b>انتخاب پنل</b>\n\nپنل مورد نظر برای این پلن را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm_select_plan_panel_"))
async def cb_select_plan_panel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    panel_id_str = callback.data.split("_")[-1]
    if panel_id_str == "default":
        from api import panel_manager
        panel = panel_manager.get_default()
        if not panel:
            await callback.answer("پنل پیش‌فرض یافت نشد!", show_alert=True)
            return
        panel_id = panel.panel_id
    else:
        panel_id = int(panel_id_str)
    await state.update_data(plan_panel_id=panel_id)
    from api import panel_manager
    panel = panel_manager.get(panel_id) or panel_manager.get_default()
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return
    try:
        loop = asyncio.new_event_loop()
        login_ok = loop.run_until_complete(panel.login())
        if login_ok:
            inbounds = loop.run_until_complete(panel.get_inbounds())
        else:
            inbounds = None
        loop.close()
    except Exception:
        inbounds = None
    if not inbounds:
        await state.update_data(plan_inbound_ids="")
        await state.set_state(AdminState.add_plan_ip_limit)
        await callback.message.edit_text(
            "⚠️ اینباندی یافت نشد. محدودیت IP را وارد کنید\n(۰ = بدون محدودیت):",
            parse_mode="HTML",
        )
        await callback.answer()
        return
    await state.update_data(plan_inbounds_available=[{"id": ib["id"], "tag": ib.get("tag", "?"), "proto": ib.get("protocol", "?")} for ib in inbounds])
    await state.update_data(plan_selected_inbounds=[])
    await _show_inbound_selection(callback.message, state)
    await callback.answer()


async def _show_inbound_selection(target, state: FSMContext):
    """Show inbound multi-select keyboard."""
    data = await state.get_data()
    available = data.get("plan_inbounds_available", [])
    selected = set(data.get("plan_selected_inbounds", []))
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for ib in available:
        icon = "✅" if ib["id"] in selected else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} ID: {ib['id']} — {ib['tag']} ({ib['proto']})",
            callback_data=f"adm_toggle_ib_{ib['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="✅ تأیید انتخاب", callback_data="adm_confirm_inbounds")])
    buttons.append([InlineKeyboardButton(text="⏭️ رد کردن (بدون اینباند)", callback_data="adm_skip_inbounds")])
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📡 <b>انتخاب اینباندها</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  اینباندهای مورد نظر را کلیک کنید:\n"
        f"  ( روی هر کدام کلیک کنید تا فعال/غیرفعال شود )\n"
    )
    try:
        await target.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await target.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("adm_toggle_ib_"))
async def cb_toggle_inbound(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    ib_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    selected = set(data.get("plan_selected_inbounds", []))
    if ib_id in selected:
        selected.discard(ib_id)
    else:
        selected.add(ib_id)
    await state.update_data(plan_selected_inbounds=list(selected))
    await _show_inbound_selection(callback.message, state)


@router.callback_query(F.data == "adm_confirm_inbounds")
async def cb_confirm_inbounds(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    selected = data.get("plan_selected_inbounds", [])
    inbound_str = ",".join(str(x) for x in selected) if selected else ""
    await state.update_data(plan_inbound_ids=inbound_str)
    await state.set_state(AdminState.add_plan_ip_limit)
    await callback.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔒 <b>محدودیت IP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "  حداکثر تعداد IP همزمان برای این پلن:\n"
        "  (۰ = بدون محدودیت)\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="0 — بدون محدودیت", callback_data="adm_ip_0"),
                InlineKeyboardButton(text="1", callback_data="adm_ip_1"),
            ],
            [
                InlineKeyboardButton(text="2", callback_data="adm_ip_2"),
                InlineKeyboardButton(text="3", callback_data="adm_ip_3"),
            ],
            [
                InlineKeyboardButton(text="5", callback_data="adm_ip_5"),
                InlineKeyboardButton(text="10", callback_data="adm_ip_10"),
            ],
            [InlineKeyboardButton(text="✏️ عدد دیگر", callback_data="adm_ip_custom")],
        ])
    )


@router.callback_query(F.data == "adm_skip_inbounds")
async def cb_skip_inbounds(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.update_data(plan_inbound_ids="")
    await state.set_state(AdminState.add_plan_ip_limit)
    await callback.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔒 <b>محدودیت IP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "  حداکثر تعداد IP همزمان:\n"
        "  (۰ = بدون محدودیت)\n",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="0 — بدون محدودیت", callback_data="adm_ip_0"),
                InlineKeyboardButton(text="1", callback_data="adm_ip_1"),
            ],
            [
                InlineKeyboardButton(text="2", callback_data="adm_ip_2"),
                InlineKeyboardButton(text="3", callback_data="adm_ip_3"),
            ],
            [
                InlineKeyboardButton(text="5", callback_data="adm_ip_5"),
                InlineKeyboardButton(text="10", callback_data="adm_ip_10"),
            ],
            [InlineKeyboardButton(text="✏️ عدد دیگر", callback_data="adm_ip_custom")],
        ])
    )


@router.callback_query(F.data.startswith("adm_ip_"))
async def cb_select_ip_limit(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    cb_data = callback.data
    if cb_data == "adm_ip_custom":
        await callback.message.edit_text("🔒 عدد محدودیت IP را وارد کنید (۰ = بدون محدودیت):")
        return
    ip_limit = int(cb_data.split("_")[-1])
    await _ask_collab_price(callback.message, state, ip_limit)


@router.message(AdminState.add_plan_ip_limit)
async def process_plan_ip_limit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        ip_limit = int(message.text.strip())
        if ip_limit < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد غیرمنفی وارد کنید:")
        return
    await _ask_collab_price(message, state, ip_limit)


async def _ask_collab_price(target, state: FSMContext, ip_limit: int):
    await state.update_data(plan_ip_limit=ip_limit)
    await state.set_state(AdminState.add_plan_collab_price)
    symbol = await get_setting("currency_symbol") or "تومان"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  👥 <b>قیمت همکاری</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  قیمت ویژه همکاران را به {symbol} وارد کنید:\n"
        f"  (۰ = بدون قیمت همکاری، از قیمت عادی استفاده شود)\n"
    )
    await target.edit_text(text, parse_mode="HTML") if hasattr(target, 'edit_text') else await target.answer(text, parse_mode="HTML")


@router.message(AdminState.add_plan_collab_price)
async def process_plan_collab_price(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        collab_price = int(message.text.strip())
        if collab_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد غیرمنفی وارد کنید:")
        return
    data = await state.get_data()
    ip_limit = data.get("plan_ip_limit", 0)
    await _finalize_plan(message, state, ip_limit)


async def _finalize_plan(target, state: FSMContext, ip_limit: int):
    data = await state.get_data()
    inbound_str = data.get("plan_inbound_ids", "")
    panel_id = data.get("plan_panel_id")
    service_type = data.get("plan_service_type", "v2ray")
    collab_price = data.get("plan_collab_price", 0)
    plan_id = await add_plan(
        data["plan_name"], data["plan_gb"], data["plan_days"],
        data["plan_price"], inbound_ids=inbound_str, ip_limit=ip_limit, panel_id=panel_id,
        service_type=service_type, collaborator_price=collab_price,
    )
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    ib_text = inbound_str if inbound_str else "پیش‌فرض"
    ip_text = f"{ip_limit}" if ip_limit > 0 else "بدون محدودیت"
    collab_text = f"{collab_price:,} {symbol}" if collab_price > 0 else "غیرفعال"
    plans = await get_all_plans()
    await target.answer(
        f"✅ پلن <b>{data['plan_name']}</b> ایجاد شد!\n\n"
        f"📊 حجم: {data['plan_gb']} GB\n"
        f"📅 مدت: {data['plan_days']} روز\n"
        f"💰 قیمت: {data['plan_price']:,} {symbol}\n"
        f"👥 قیمت همکاری: {collab_text}\n"
        f"📡 اینباندها: {ib_text}\n"
        f"🔒 محدودیت IP: {ip_text}",
        parse_mode="HTML", reply_markup=await plans_menu(plans)
    )


@router.callback_query(F.data.startswith("adm_edit_plan_"))
async def cb_edit_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ پلن یافت نشد!", show_alert=True)
        return
    await state.update_data(edit_plan_id=plan_id)
    await state.set_state(AdminState.edit_plan_field)
    symbol = await get_setting("currency_symbol") or "تومان"
    collab = plan.get("collaborator_price", 0)
    collab_display = f" | {collab}" if collab else ""
    await callback.message.edit_text(
        f"✏️ <b>ویرایش پلن: {plan['name']}</b>\n\n"
        f"مقادیر جدید را به این فرمت وارد کنید:\n"
        f"<code>نام | حجم | روز | قیمت</code>\n"
        f"یا با قیمت همکاری:\n"
        f"<code>نام | حجم | روز | قیمت | قیمت همکاری</code>\n\n"
        f"مثال: <code>۱ ماهه | 50 | 30 | 150000 | 120000</code>\n"
        f"فعلی: <code>{plan['name']} | {plan['gb']} | {plan['days']} | {plan['price']}{collab_display}</code>",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_plan_field)
async def process_edit_plan(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    plan_id = data.get("edit_plan_id")
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) not in (4, 5):
            raise ValueError
        name = parts[0]
        gb = int(parts[1])
        days = int(parts[2])
        price = int(parts[3])
        collab_price = int(parts[4]) if len(parts) == 5 else 0
        if gb <= 0 or days <= 0 or price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ فرمت نامعتبر. از فرمت <code>نام | حجم | روز | قیمت</code> یا <code>نام | حجم | روز | قیمت | قیمت همکاری</code> استفاده کنید:", parse_mode="Markdown")
        return
    await update_plan(plan_id, name=name, gb=gb, days=days, price=price, collaborator_price=collab_price)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    collab_text = f" | همکاری: {collab_price:,}" if collab_price else ""
    plans = await get_all_plans()
    await message.answer(
        f"✅ پلن به‌روزرسانی شد: <b>{name}</b> | {gb}GB | {days} روز | {price:,} {symbol}{collab_text}",
        parse_mode="HTML", reply_markup=await plans_menu(plans)
    )


@router.callback_query(F.data.startswith("adm_delete_plan_"))
async def cb_delete_plan(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    plan_id = int(callback.data.split("_")[-1])
    await delete_plan(plan_id)
    await callback.answer("✅ پلن حذف شد!", show_alert=True)
    plans = await get_all_plans()
    await callback.message.edit_text("📦 <b>مدیریت پلن‌ها</b>", parse_mode="HTML", reply_markup=await plans_menu(plans))


@router.callback_query(F.data.startswith("adm_toggle_plan_"))
async def cb_toggle_plan(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ پلن یافت نشد!", show_alert=True)
        return
    await update_plan(plan_id, is_active=not plan["is_active"])
    status = "فعال ✅" if not plan["is_active"] else "غیرفعال ❌"
    await callback.answer(f"وضعیت پلن: {status}", show_alert=True)
    plans = await get_all_plans()
    await callback.message.edit_text("📦 <b>مدیریت پلن‌ها</b>", parse_mode="HTML", reply_markup=await plans_menu(plans))


# ─── Plan Sections ───────────────────────────────────────────
@router.callback_query(F.data == "adm_plan_sections")
async def cb_plan_sections(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    sections = await get_plan_sections()
    if not sections:
        await callback.message.edit_text("📁 <b>بخش‌های پلن</b>\n\nهیچ بخشی وجود ندارد.", parse_mode="HTML", reply_markup=await back_to_admin())
        return
    await callback.message.edit_text("📁 <b>بخش‌های پلن</b>", parse_mode="HTML", reply_markup=await plan_sections_menu(sections))


@router.callback_query(F.data == "adm_add_plan_section")
async def cb_add_section(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_plan_section_name)
    await callback.message.edit_text("📁 <b>افزودن بخش جدید</b>\n\nنام بخش را وارد کنید:", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.add_plan_section_name)
async def process_add_section(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await add_plan_section(message.text.strip())
    await state.clear()
    sections = await get_plan_sections()
    await message.answer(f"✅ بخش <b>{message.text.strip()}</b> ایجاد شد!", parse_mode="HTML", reply_markup=await plan_sections_menu(sections))


@router.callback_query(F.data.startswith("adm_plan_section_"))
async def cb_section_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    section_id = int(callback.data.split("_")[-1])
    section = await get_plan_section(section_id)
    if not section:
        await callback.answer("❌ بخش یافت نشد!", show_alert=True)
        return
    await callback.message.edit_text(
        f"📁 <b>{section['name']}</b>\n\nترتیب نمایش: {section['display_order']}",
        parse_mode="HTML", reply_markup=await plan_section_actions(section_id)
    )


@router.callback_query(F.data.startswith("adm_delete_section_"))
async def cb_delete_section(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    section_id = int(callback.data.split("_")[-1])
    await delete_plan_section(section_id)
    await callback.answer("✅ بخش حذف شد!", show_alert=True)
    sections = await get_plan_sections()
    await callback.message.edit_text("📁 <b>بخش‌های پلن</b>", parse_mode="HTML", reply_markup=await plan_sections_menu(sections))


# ═══════════════════════════════════════════════════════════════
# SECTION 4: Receipts Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_receipts_menu")
async def cb_receipts_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    pending = await get_pending_receipts()
    await callback.message.edit_text("📋 <b>مدیریت رسیدها</b>", parse_mode="HTML", reply_markup=await receipts_menu(len(pending)))


@router.callback_query(F.data.startswith("adm_receipts_"))
async def cb_receipts_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    status = callback.data.replace("adm_receipts_", "")
    from database import get_db
    db = await get_db()
    if status == "pending":
        cursor = await db.execute("SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id WHERE r.status = 'pending' ORDER BY r.created_at DESC LIMIT 10")
    elif status == "all":
        cursor = await db.execute("SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC LIMIT 10")
    elif status in ("approved", "rejected"):
        cursor = await db.execute("SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id WHERE r.status = ? ORDER BY r.created_at DESC LIMIT 10", (status,))
    else:
        cursor = await db.execute("SELECT r.*, u.username FROM receipts r LEFT JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC LIMIT 10")
    receipts = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    if not receipts:
        await callback.message.edit_text(f"📋 <b>رسیدهای {status}</b>\n\nهیچ رسیدی یافت نشد.", parse_mode="HTML", reply_markup=await receipts_menu(0))
        return
    await callback.message.edit_text(f"📋 <b>رسیدهای {status}</b>", parse_mode="HTML", reply_markup=await receipt_list_keyboard(receipts, status))


@router.callback_query(F.data.startswith("adm_view_receipt_"))
async def cb_view_receipt(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("❌ رسید یافت نشد!", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    status_icons = {"pending": "⏳ در انتظار", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
    status_text = status_icons.get(receipt["status"], "نامشخص")
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📋 <b>رسید #{receipt['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👤 کاربر: <code>{receipt['user_id']}</code>\n"
        f"  💰 مبلغ: <b>{receipt['amount']:,.0f} {symbol}</b>\n"
        f"  📅 تاریخ: {receipt['created_at'][:16]}\n"
        f"  📌 وضعیت: <b>{status_text}</b>"
    )
    kb = await receipt_actions(receipt_id) if receipt["status"] == "pending" else await back_to_admin()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=receipt["photo_file_id"],
        caption=text, parse_mode="HTML", reply_markup=kb,
    )


@router.callback_query(F.data.startswith("adm_approve_"))
async def cb_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("❌ رسید یافت نشد!", show_alert=True)
        return
    await approve_receipt(receipt_id, callback.from_user.id)
    symbol = await get_setting("currency_symbol") or "تومان"
    try:
        if receipt["plan_id"] and receipt["plan_id"] > 0:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 ساخت کانفیگ من", callback_data=f"make_config_{receipt['plan_id']}")],
            ])
            await callback.bot.send_message(
                chat_id=receipt["user_id"],
                text=f"✅ رسید شما تایید شد! ({receipt['amount']:,.0f} {symbol})\n\nروی دکمه زیر کلیک کنید:",
                reply_markup=kb,
            )
        else:
            from utils.texts import receipt_approved
            user = await get_user(receipt["user_id"])
            new_balance = user["balance"] if user else 0
            await callback.bot.send_message(
                chat_id=receipt["user_id"],
                text=await receipt_approved(receipt["amount"], new_balance, symbol),
            )
    except Exception:
        pass
    await callback.answer("✅ رسید تایید شد!", show_alert=True)
    await callback.message.edit_caption(caption=f"✅ <b>رسید #{receipt_id} تایید شد</b>", parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("adm_reject_"))
async def cb_reject(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("❌ رسید یافت نشد!", show_alert=True)
        return
    await reject_receipt(receipt_id, callback.from_user.id)
    symbol = await get_setting("currency_symbol") or "تومان"
    try:
        from utils.texts import receipt_rejected
        await callback.bot.send_message(
            chat_id=receipt["user_id"],
            text=await receipt_rejected(receipt["amount"], symbol),
        )
    except Exception:
        pass
    await callback.answer("❌ رسید رد شد!", show_alert=True)
    await callback.message.edit_caption(caption=f"❌ <b>رسید #{receipt_id} رد شد</b>", parse_mode="HTML", reply_markup=await back_to_admin())


# ═══════════════════════════════════════════════════════════════
# SECTION 5: Config Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_configs")
async def cb_configs(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔑 <b>مدیریت کانفیگ‌ها</b>", parse_mode="HTML", reply_markup=await configs_menu())


@router.callback_query(F.data == "adm_all_configs_list")
async def cb_all_configs_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from database import get_db
    db = await get_db()
    cursor = await db.execute(
        "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC LIMIT 15"
    )
    configs = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    if not configs:
        await callback.message.edit_text("🔑 <b>لیست کانفیگ‌ها</b>\n\nهیچ کانفیگی وجود ندارد.", parse_mode="HTML", reply_markup=await back_to_admin())
        return
    await callback.message.edit_text("🔑 <b>لیست کانفیگ‌ها</b>", parse_mode="HTML", reply_markup=await config_list_keyboard(configs))


@router.callback_query(F.data.startswith("adm_cfg_detail_"))
async def cb_cfg_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    config_id = int(callback.data.split("_")[-1])
    from database import get_config_by_id
    cfg = await get_config_by_id(config_id)
    if not cfg:
        await callback.answer("❌ کانفیگ یافت نشد!", show_alert=True)
        return
    status = "🟢 فعال" if cfg["is_active"] else "🔴 غیرفعال"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🔑 <b>کانفیگ #{cfg['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📧 ایمیل: <code>{cfg['email']}</code>\n"
        f"  📅 انقضا: <b>{cfg['expire_date'][:10]}</b>\n"
        f"  📌 وضعیت: <b>{status}</b>\n"
        f"  👤 کاربر: <code>{cfg['user_id']}</code>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await config_actions(config_id))


@router.callback_query(F.data.startswith("adm_deactivate_cfg_"))
async def cb_deactivate_cfg(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    config_id = int(callback.data.split("_")[-1])
    from database import deactivate_config
    await deactivate_config(config_id)
    await callback.answer("🔴 کانفیگ غیرفعال شد!", show_alert=True)
    await callback.message.edit_text("🔑 <b>مدیریت کانفیگ‌ها</b>", parse_mode="HTML", reply_markup=await configs_menu())


@router.callback_query(F.data.startswith("adm_delete_cfg_"))
async def cb_delete_cfg(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    config_id = int(callback.data.split("_")[-1])
    from database import delete_config
    await delete_config(config_id)
    await callback.answer("🗑️ کانفیگ حذف شد!", show_alert=True)
    await callback.message.edit_text("🔑 <b>مدیریت کانفیگ‌ها</b>", parse_mode="HTML", reply_markup=await configs_menu())


@router.callback_query(F.data == "adm_search_config")
async def cb_search_config(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.search_config)
    await callback.message.edit_text(
        "🔍 <b>جستجوی کانفیگ</b>\n\nآیدی کانفیگ یا ایمیل کاربر را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.search_config)
async def process_search_config(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    from database import get_db
    db = await get_db()
    try:
        config_id = int(message.text.strip())
        cursor = await db.execute("SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id WHERE c.id = ?", (config_id,))
    except ValueError:
        cursor = await db.execute("SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id WHERE c.email LIKE ?", (f"%{message.text.strip()}%",))
    configs = [dict(r) for r in await cursor.fetchall()]
    await db.close()
    if not configs:
        await message.answer("❌ کانفیگی یافت نشد.", reply_markup=await back_to_admin())
        return
    await message.answer("🔑 <b>نتایج جستجو</b>", parse_mode="HTML", reply_markup=await config_list_keyboard(configs))


# ═══════════════════════════════════════════════════════════════
# SECTION 6: Admin Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_admins")
async def cb_admins(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    admins = await get_admins()
    await callback.message.edit_text("🛡️ <b>مدیریت ادمین‌ها</b>", parse_mode="HTML", reply_markup=await admins_menu(admins))


@router.callback_query(F.data == "adm_add_admin")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_admin_id)
    await callback.message.edit_text(
        "➕ <b>افزودن ادمین</b>\n\nآیدی عددی تلگرام کاربر را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.add_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ آیدی نامعتبر. یک عدد وارد کنید:")
        return
    await add_admin(user_id, None)
    await state.clear()
    admins = await get_admins()
    await message.answer(f"✅ کاربر <code>{user_id}</code> به عنوان ادمین اضافه شد!", parse_mode="HTML", reply_markup=await admins_menu(admins))


@router.callback_query(F.data.startswith("adm_admin_detail_"))
async def cb_admin_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    admin_id = int(callback.data.split("_")[-1])
    user = await get_user(admin_id)
    uname = f"@{user.get('username', 'ندارد')}" if user else "نامشخص"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ حذف ادمین", callback_data=f"adm_remove_admin_{admin_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_admins")],
    ])
    await callback.message.edit_text(
        f"🛡️ <b>ادمین: {uname}</b>\n\nآیدی: <code>{admin_id}</code>",
        parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data.startswith("adm_remove_admin_"))
async def cb_remove_admin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    admin_id = int(callback.data.split("_")[-1])
    if admin_id == callback.from_user.id:
        await callback.answer("❌ نمی‌توانید خودتان را حذف کنید!", show_alert=True)
        return
    await remove_admin(admin_id)
    await callback.answer("✅ ادمین حذف شد!", show_alert=True)
    admins = await get_admins()
    await callback.message.edit_text("🛡️ <b>مدیریت ادمین‌ها</b>", parse_mode="HTML", reply_markup=await admins_menu(admins))


# ═══════════════════════════════════════════════════════════════
# SECTION 7: Settings
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_settings")
async def cb_settings(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("⚙️ <b>تنظیمات ربات</b>", parse_mode="HTML", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_edit_welcome")
async def cb_edit_welcome(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("welcome_text") or ""
    await state.set_state(AdminState.edit_welcome)
    await callback.message.edit_text(
        f"📝 <b>متن خوش‌آمدگویی</b>\n\nمتن فعلی:\n<code>{current[:200]}</code>\n\nمتن جدید را ارسال کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_welcome)
async def process_edit_welcome(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("welcome_text", message.text)
    await state.clear()
    await message.answer("✅ متن خوش‌آمدگویی به‌روزرسانی شد!", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_edit_welcome_emoji")
async def cb_edit_welcome_emoji(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("welcome_emoji") or ""
    await state.set_state(AdminState.edit_welcome_emoji)
    await callback.message.edit_text(
        f"🎯 <b>ایموجی خوش‌آمدگویی</b>\n\n"
        f"فعلی: <code>{current if current else 'غیرفعال'}</code>\n\n"
        f"ایموجی مورد نظر را ارسال کنید:\n"
        f"<b>نحوه دریافت آیدی ایموجی پرمیوم:</b>\n"
        f"1. ایموجی پرمیوم مورد نظر را در چت خصوصی ارسال کنید\n"
        f"2. آن را به ربات <code>@customemojiids</code> فوروارد کنید\n"
        f"3. آیدی دریافتی را کپی کنید\n\n"
        f"<b>یا:</b> ایموجی پرمیوم را همینجا ارسال کنید\n\n"
        f"(برای غیرفعال کردن `غیرفعال` تایپ کنید)",
        f"(برای غیرفعال کردن `غیرفعال` تایپ کنید)",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_welcome_emoji)
async def process_edit_welcome_emoji(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    value = message.text.strip()
    if value == "غیرفعال":
        await set_setting("welcome_emoji", "")
        await message.answer("✅ ایموجی خوش‌آمدگویی غیرفعال شد!", reply_markup=await settings_menu())
        await state.clear()
        return

    # Try to extract custom_emoji_id from message entities
    emoji_id = None
    if message.entities:
        for ent in message.entities:
            if ent.type == "custom_emoji":
                emoji_id = str(ent.custom_emoji_id)
                break

    if emoji_id:
        await set_setting("welcome_emoji", emoji_id)
        await message.answer(f"✅ ایموجی پرمیوم ذخیره شد! (ID: <code>{emoji_id}</code>)", parse_mode="HTML", reply_markup=await settings_menu())
    else:
        await set_setting("welcome_emoji", value)
        await message.answer(f"⚠️ ایموجی معمولی ذخیره شد (پشتیبانی نمی‌شود).\nلطفاً یک <b>ایموجی پرمیوم</b> ارسال کنید.", parse_mode="HTML", reply_markup=await settings_menu())
    await state.clear()


@router.callback_query(F.data == "adm_edit_payment")
async def cb_edit_payment(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("💳 <b>اطلاعات پرداخت</b>", parse_mode="HTML", reply_markup=await payment_settings_menu())


@router.callback_query(F.data == "adm_edit_card_number")
async def cb_edit_card_number(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("card_number") or ""
    await state.set_state(AdminState.edit_card_number)
    await callback.message.edit_text(
        f"💳 <b>شماره کارت</b>\n\nفعلی: <code>{current}</code>\n\nشماره جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_card_number)
async def process_edit_card_number(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("card_number", message.text.strip())
    await state.clear()
    await message.answer("✅ شماره کارت به‌روزرسانی شد!", reply_markup=await payment_settings_menu())


@router.callback_query(F.data == "adm_edit_card_owner")
async def cb_edit_card_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("card_owner") or ""
    await state.set_state(AdminState.edit_card_owner)
    await callback.message.edit_text(
        f"👤 <b>نام صاحب کارت</b>\n\nفعلی: <b>{current}</b>\n\nنام جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_card_owner)
async def process_edit_card_owner(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("card_owner", message.text.strip())
    await state.clear()
    await message.answer("✅ نام صاحب کارت به‌روزرسانی شد!", reply_markup=await payment_settings_menu())


@router.callback_query(F.data == "adm_edit_c2c_title")
async def cb_edit_c2c_title(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.edit_c2c_title)
    await callback.message.edit_text("✏️ <b>عنوان کارت به کارت</b>\n\nعنوان جدید را وارد کنید:", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.edit_c2c_title)
async def process_edit_c2c_title(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("c2c_title", message.text.strip())
    await state.clear()
    await message.answer("✅ عنوان به‌روزرسانی شد!", reply_markup=await payment_settings_menu())


@router.callback_query(F.data == "adm_edit_c2c_instruction")
async def cb_edit_c2c_instruction(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.edit_c2c_instruction)
    await callback.message.edit_text("✏️ <b>راهنمای کارت به کارت</b>\n\nمتن جدید را وارد کنید:", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.edit_c2c_instruction)
async def process_edit_c2c_instruction(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("c2c_instruction", message.text.strip())
    await state.clear()
    await message.answer("✅ راهنما به‌روزرسانی شد!", reply_markup=await payment_settings_menu())


@router.callback_query(F.data == "adm_edit_free_test")
async def cb_edit_free_test(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🧪 <b>مدیریت تست رایگان</b>\n\nتنظیمات کامل طرح تست رایگان را مدیریت کنید:",
        parse_mode="HTML", reply_markup=await trial_management_menu()
    )


@router.callback_query(F.data == "adm_trial_toggle")
async def cb_trial_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("free_test_enabled") or "1"
    new_val = "0" if current == "1" else "1"
    await set_setting("free_test_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"تست رایگان {status}", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=await trial_management_menu())


@router.callback_query(F.data == "adm_trial_edit_mb")
async def cb_trial_edit_mb(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("free_test_mb") or "102400"
    await state.set_state(AdminState.edit_free_test_mb)
    await callback.message.edit_text(
        f"🧪 <b>حجم تست رایگان</b>\n\nفعلی: <b>{current} MB</b>\n\nحجم جدید (MB) را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_free_test_mb)
async def process_edit_free_test_mb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        mb = int(message.text.strip())
        if mb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتر. یک عدد مسبب وارد کنید:")
        return
    await set_setting("free_test_mb", str(mb))
    await state.clear()
    await message.answer("✅ بروزرسانی شد!", reply_markup=await trial_management_menu())


@router.callback_query(F.data == "adm_trial_edit_days")
async def cb_trial_edit_days(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("free_test_days") or "1"
    await state.set_state(AdminState.edit_trial_days)
    await callback.message.edit_text(
        f"📅 <b>مدت تست رایگان</b>\n\nفعلی: <b>{current} روز</b>\n\nمدت جدید (روز) را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_trial_days)
async def process_edit_trial_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتر. یک عدد مسبب وارد کنید:")
        return
    await set_setting("free_test_days", str(days))
    await state.clear()
    await message.answer("✅ بروزرسانی شد!", reply_markup=await trial_management_menu())


@router.callback_query(F.data == "adm_trial_edit_inbounds")
async def cb_trial_edit_inbounds(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("free_test_inbound_ids") or ""
    display = current if current else "پیشاًدفلت پنل (خالی)"
    await state.set_state(AdminState.edit_trial_inbounds)
    await callback.message.edit_text(
        f"🔗 <b>ردیف‌های تست رایگان</b>\n\n"
        f"فعلی: <code>{display}</code>\n\n"
        f"ردیف‌های جدید را با کاما جدا کنید (مثال: <code>30,42</code>)\n"
        f"برای استفاده از پیشاًدفلت پنل، بنویسید: <code>-</code>",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_trial_inbounds)
async def process_edit_trial_inbounds(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text == "-":
        await set_setting("free_test_inbound_ids", "")
        await message.answer("✅ از پیشاًدفلت پنل استفاده میشود.", reply_markup=await trial_management_menu())
    else:
        parts = [x.strip() for x in text.split(",") if x.strip().isdigit()]
        if not parts:
            await message.answer("❌ فرمت نامعتر. ردیف‌ها را با کاما جدا کنید (مثال: <code>30,42</code>):", parse_mode="HTML")
            return
        await set_setting("free_test_inbound_ids", ",".join(parts))
        await message.answer(f"✅ ردیف‌ها: <code>{','.join(parts)}</code>", parse_mode="HTML", reply_markup=await trial_management_menu())
    await state.clear()


@router.callback_query(F.data == "adm_trial_users")
async def cb_trial_users(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    users = await get_free_test_users()
    if not users:
        await callback.answer("هیچ کاربری تست رایگان نگرفته است.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for u in users[:20]:
        uid = u["user_id"]
        uname = u.get("username") or u.get("first_name") or str(uid)
        ts = u.get("created_at", "")[:10] if u.get("created_at") else ""
        btn_text = f"@{uname} — {ts}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_trial_user_{uid}")])
    buttons.append([await _btn("🔄 ریست همه کاربران", "adm_trial_reset_all", "gear")])
    buttons.append([await _btn("🔙 بازگشت", "adm_edit_free_test", btn_id="back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(f"👥 <b>کاربران تست رایگان</b> ({len(users)} نفر)", parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_trial_user_"))
async def cb_trial_user_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    uid = int(callback.data.split("_")[-1])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [await _btn(f"🔄 ریست تست کاربر {uid}", f"adm_trial_reset_user_{uid}", "gear")],
        [await _btn("🔙 بازگشت", "adm_trial_users", btn_id="back")],
    ])
    await callback.message.edit_text(f"👤 <b>کاربر {uid}</b>\n\nبرای ریست تست رایگان این کاربر، روی دکمه زیر کلیک کنید:", parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_trial_reset_user_"))
async def cb_trial_reset_user(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    uid = int(callback.data.split("_")[-1])
    await reset_free_test(uid)
    await callback.answer(f"✅ تست کاربر {uid} ریست شد.", show_alert=True)
    await cb_trial_user_detail(callback)


@router.callback_query(F.data == "adm_trial_reset_all")
async def cb_trial_reset_all(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "⚠️ <b>آیا مطمئن هستید؟</b>\n\nتمام کانفیگ‌های تست رایگان حذف خواهند شد و همه کاربران می‌توانند دوباره تست بگیرند.",
        parse_mode="HTML",
        reply_markup=await confirm_action("adm_trial_reset_all_confirm", "آیا مطمئن هستید؟")
    )


@router.callback_query(F.data == "adm_trial_reset_all_confirm")
async def cb_trial_reset_all_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    count = await reset_all_free_tests()
    await callback.answer(f"✅ {count} کانفیگ تست حذف شد.", show_alert=True)
    await callback.message.edit_text("<b>✅ همه تست‌های رایگان ریست شدند.</b>", parse_mode="HTML", reply_markup=await trial_management_menu())



async def cb_edit_auto_approve(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("auto_approve_max") or "0"
    symbol = await get_setting("currency_symbol") or "تومان"
    status = f"{float(current):,.0f} {symbol}" if float(current) > 0 else "غیرفعال"
    await state.set_state(AdminState.edit_auto_approve)
    await callback.message.edit_text(
        f"✅ <b>تایید خودکار</b>\n\nحد فعلی: <b>{status}</b>\n\nرسیدهای تا این مبلغ خودکار تایید می‌شوند.\n۰ = غیرفعال\n\nمبلغ جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_auto_approve)
async def process_edit_auto_approve(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip())
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت یا ۰ وارد کنید:")
        return
    await set_setting("auto_approve_max", str(amount))
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    if amount > 0:
        await message.answer(f"✅ تایید خودکار: <b>{amount:,.0f} {symbol}</b>", parse_mode="HTML", reply_markup=await settings_menu())
    else:
        await message.answer("✅ تایید خودکار غیرفعال شد.", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_edit_buttons")
async def cb_edit_buttons(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎨 <b>ویرایش دکمه‌ها</b>\n\nدکمه مورد نظر را انتخاب کنید:", parse_mode="HTML", reply_markup=await buttons_editor_menu())


BUTTON_SETTINGS = {
    "adm_edit_btn_start": "btn_start",
    "adm_edit_btn_wallet": "btn_wallet",
    "adm_edit_btn_free_test": "btn_free_test",
    "adm_edit_btn_buy_config": "btn_buy_config",
    "adm_edit_btn_my_configs": "btn_my_configs",
    "adm_edit_btn_collab": "btn_collab_request",
    "adm_edit_btn_topup": "btn_topup",
    "adm_edit_btn_tx_history": "btn_tx_history",
    "adm_edit_btn_back": "btn_back",
    "adm_edit_btn_back_to_menu": "btn_back_to_menu",
    "adm_edit_btn_support": "btn_support",
    "adm_edit_btn_tutorials": "btn_tutorials",
}


@router.callback_query(F.data.startswith("adm_edit_btn_"))
async def cb_edit_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    setting_key = BUTTON_SETTINGS.get(callback.data)
    if not setting_key:
        await callback.answer("ناشناخته!", show_alert=True)
        return
    current = await get_setting(setting_key) or ""
    await state.update_data(button_key=setting_key)
    await state.set_state(AdminState.edit_button_name)
    await callback.message.edit_text(
        f"🎨 <b>ویرایش دکمه</b>\n\nمتن فعلی: <b>{current}</b>\n\nمتن جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_button_name)
async def process_edit_button(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("button_key")
    if key:
        await set_setting(key, message.text)
    await state.clear()
    await message.answer(f"✅ دکمه به‌روزرسانی شد: <b>{message.text}</b>", parse_mode="HTML", reply_markup=await buttons_editor_menu())


@router.callback_query(F.data == "adm_edit_bot_texts")
async def cb_edit_bot_texts(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📝 <b>متن‌های ربات</b>\n\nمتن مورد نظر را انتخاب کنید:", parse_mode="HTML", reply_markup=await bot_texts_menu())


BOT_TEXT_KEYS = {
    "adm_text_welcome": ("welcome_text", "متن خوش‌آمدگویی"),
    "adm_text_wallet": ("text_wallet", "متن کیف پول"),
    "adm_text_receipt_approved": ("text_receipt_approved", "متن تایید رسید"),
    "adm_text_receipt_rejected": ("text_receipt_rejected", "متن رد رسید"),
    "adm_text_config_created": ("text_config_created", "متن ساخت کانفیگ"),
    "adm_text_free_test": ("text_free_test", "متن تست رایگان"),
    "adm_text_new_user": ("text_new_user_notification", "متن کاربر جدید"),
}


@router.callback_query(F.data.startswith("adm_text_"))
async def cb_edit_bot_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    info = BOT_TEXT_KEYS.get(callback.data)
    if not info:
        return
    key, label = info
    current = await get_setting(key) or "(پیش‌فرض)"
    await state.update_data(bot_text_key=key)
    await state.set_state(AdminState.edit_bot_text_key)
    await callback.message.edit_text(
        f"📝 <b>{label}</b>\n\nمتن فعلی:\n<code>{current[:300]}</code>\n\nمتن جدید را ارسال کنید.\nبرای بازگشت به متن پیش‌فرض، بنویسید: <code>پیش‌فرض</code>",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_bot_text_key)
async def process_edit_bot_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("bot_text_key")
    if key:
        value = "" if message.text.strip() == "پیش‌فرض" else message.text
        await set_setting(key, value)
    await state.clear()
    await message.answer("✅ متن به‌روزرسانی شد!", reply_markup=await bot_texts_menu())


@router.callback_query(F.data == "adm_edit_premium_emojis")
async def cb_edit_premium_emojis(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎭 <b>ایموجی‌های پرمیوم</b>", parse_mode="HTML", reply_markup=await premium_emojis_menu())


@router.callback_query(F.data == "adm_send_emoji_register")
async def cb_send_emoji_register(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_emoji_name)
    await callback.message.edit_text(
        "⭐ <b>ثبت ایموجی پرمیوم</b>\n\nنام ایموجی را وارد کنید (مثال: wallet):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.waiting_emoji_name)
async def process_emoji_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    valid_names = [
        "wallet", "free_test", "buy_config", "my_configs", "back", "admin",
        "stats", "users", "settings", "plans", "receipts", "admins", "check", "cross",
        "card", "owner", "star", "copy", "cancel", "success", "approve", "reject",
        "ban", "unban", "plus", "minus", "list", "gear", "money", "calendar", "history",
        "menu", "package", "link", "clock", "start", "copy_number", "copy_price",
    ]
    name = message.text.strip().lower()
    if name not in valid_names:
        await message.answer(f"❌ نام نامعتبر. یکی از این‌ها را استفاده کنید:\n<code>{', '.join(valid_names[:20])}</code>", parse_mode="HTML")
        return
    await state.update_data(emoji_name=name)
    await state.set_state(AdminState.waiting_emoji_id)
    await message.answer(f"⭐ نام: <b>{name}</b>\n\nحالا ایموجی پرمیوم را ارسال کنید.", parse_mode="HTML")


@router.message(AdminState.waiting_emoji_id)
async def process_emoji_receive(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    emoji_name = data.get("emoji_name", "")
    if not emoji_name:
        await state.clear()
        await message.answer("❌ مشکلی پیش آمد. دوباره شروع کنید.")
        return
    for entity in (message.entities or []) + (message.caption_entities or []):
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            from utils.premium_emoji import register_premium_emoji
            await register_premium_emoji(emoji_name, entity.custom_emoji_id)
            await state.clear()
            await message.answer(
                f"✅ ایموجی ثبت شد: <b>{emoji_name}</b> → <code>{entity.custom_emoji_id}</code>",
                parse_mode="HTML", reply_markup=await premium_emojis_menu()
            )
            return
    await state.clear()
    await message.answer("❌ ایموجی پرمیوم یافت نشد. یک پیام با ایموجی پرمیوم ارسال کنید.")


@router.callback_query(F.data == "adm_view_emojis")
async def cb_view_emojis(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from utils.premium_emoji import load_emoji_ids
    mapping = await load_emoji_ids()
    if not mapping:
        text = "📋 <b>ایموجی‌های ثبت شده</b>\n\nهیچ ایموجی ثبت نشده."
    else:
        text = "📋 <b>ایموجی‌های ثبت شده</b>\n\n"
        for name, eid in mapping.items():
            text += f"  {name}: <code>{eid}</code>\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await premium_emojis_menu())


@router.callback_query(F.data == "adm_clear_emojis")
async def cb_clear_emojis(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from utils.premium_emoji import save_emoji_ids
    await save_emoji_ids({})
    await callback.answer("✅ همه ایموجی‌ها پاک شدند!", show_alert=True)
    await callback.message.edit_text("🎭 <b>ایموجی‌های پرمیوم</b>\n\nهمه ایموجی‌ها پاک شدند.", parse_mode="HTML", reply_markup=await premium_emojis_menu())


@router.callback_query(F.data == "adm_edit_force_join")
async def cb_edit_force_join(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔗 <b>عضویت اجباری در کانال</b>", parse_mode="HTML", reply_markup=await force_join_settings_menu())


@router.callback_query(F.data == "adm_toggle_force_join")
async def cb_toggle_force_join(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("force_join_enabled") or "0"
    new_val = "0" if current == "1" else "1"
    await set_setting("force_join_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"عضویت اجباری {status}", show_alert=True)
    await cb_edit_force_join(callback)


@router.callback_query(F.data == "adm_edit_required_channel")
async def cb_edit_required_channel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("required_channel_id") or ""
    await state.set_state(AdminState.edit_required_channel)
    await callback.message.edit_text(
        f"🔗 <b>شناسه کانال</b>\n\nفعلی: <code>{current}</code>\n\nشناسه جدید را وارد کنید (مثلاً @mychannel یا -1001234567890):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_required_channel)
async def process_edit_required_channel(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("required_channel_id", message.text.strip())
    await state.clear()
    await message.answer("✅ شناسه کانال به‌روزرسانی شد!", reply_markup=await force_join_settings_menu())


@router.callback_query(F.data == "adm_edit_force_join_text")
async def cb_edit_force_join_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.edit_force_join_text)
    await callback.message.edit_text("✏️ <b>متن عضویت اجباری</b>\n\nمتن جدید را وارد کنید:", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.edit_force_join_text)
async def process_edit_force_join_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("force_join_text", message.text)
    await state.clear()
    await message.answer("✅ متن به‌روزرسانی شد!", reply_markup=await force_join_settings_menu())


@router.callback_query(F.data == "adm_edit_force_join_fail_text")
async def cb_edit_force_join_fail_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.edit_force_join_fail_text)
    await callback.message.edit_text("✏️ <b>متن عدم عضویت</b>\n\nمتن جدید را وارد کنید:", parse_mode="HTML", reply_markup=await back_to_admin())


@router.message(AdminState.edit_force_join_fail_text)
async def process_edit_force_join_fail_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("force_join_fail_text", message.text)
    await state.clear()
    await message.answer("✅ متن به‌روزرسانی شد!", reply_markup=await force_join_settings_menu())




# ═══════════════════════════════════════════════════════════════
# Shop Open/Close Settings
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_toggle_shop")
async def cb_toggle_shop(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("shop_open") or "1"
    new_val = "0" if current == "1" else "1"
    await set_setting("shop_open", new_val)
    if new_val == "0":
        msg = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
        await callback.answer("فروشگاه بسته شد 🔴", show_alert=True)
        await callback.message.edit_text(
            f"🏪 <b>وضعیت فروشگاه</b>\n\n"
            f"🔴 <b>بسته</b>\n\n"
            f"متن نمایشی به کاربران:\n<code>{msg}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🟢 باز کردن فروشگاه", callback_data="adm_toggle_shop")],
                [InlineKeyboardButton(text="✏️ ویرایش متن بسته بودن", callback_data="adm_edit_shop_message")],
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_settings")],
            ]),
        )
    else:
        await callback.answer("فروشگاه باز شد 🟢", show_alert=True)
        await callback.message.edit_text(
            f"🏪 <b>وضعیت فروشگاه</b>\n\n"
            f"🟢 <b>باز</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔴 بستن فروشگاه", callback_data="adm_toggle_shop")],
                [InlineKeyboardButton(text="✏️ ویرایش متن بسته بودن", callback_data="adm_edit_shop_message")],
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_settings")],
            ]),
        )


@router.callback_query(F.data == "adm_edit_shop_message")
async def cb_edit_shop_message(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
    await state.set_state(AdminState.edit_shop_message)
    await callback.message.edit_text(
        f"✏️ <b>متن بسته بودن فروشگاه</b>\n\n"
        f"متن فعلی:\n<code>{current}</code>\n\n"
        f"متن جدید را ارسال کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_shop_message)
async def process_edit_shop_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("shop_close_message", message.text)
    await state.clear()
    await message.answer("✅ متن بسته بودن فروشگاه به‌روزرسانی شد!", reply_markup=await settings_menu())




# ═══════════════════════════════════════════════════════════════
# Invite/Referral Settings
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_edit_invite")
async def cb_edit_invite(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("👥 <b>تنظیمات زیرمجموعه گیری</b>", parse_mode="HTML", reply_markup=await invite_settings_menu())


@router.callback_query(F.data == "adm_toggle_invite")
async def cb_toggle_invite(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("invite_enabled") or "0"
    new_val = "0" if current == "1" else "1"
    await set_setting("invite_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"زیرمجموعه گیری {status}", show_alert=True)
    await callback.message.edit_text("👥 <b>تنظیمات زیرمجموعه گیری</b>", parse_mode="HTML", reply_markup=await invite_settings_menu())


@router.callback_query(F.data == "adm_edit_invite_reward")
async def cb_edit_invite_reward(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("invite_reward_amount") or "5000"
    symbol = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.edit_invite_reward)
    text = (
        f"💰 <b>مبلغ پاداش زیرمجموعه</b>\n\n"
        f"فعلی: <b>{current} {symbol}</b>\n\n"
        f"مبلغ جدید را وارد کنید:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_invite_reward)
async def process_edit_invite_reward(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip())
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت یا ۰ وارد کنید:")
        return
    await set_setting("invite_reward_amount", str(amount))
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    if amount > 0:
        await message.answer(f"✅ مبلغ پاداش: <b>{amount:,.0f} {symbol}</b>", parse_mode="HTML", reply_markup=await invite_settings_menu())
    else:
        await message.answer("✅ پاداش زیرمجموعه غیرفعال شد (مبلغ ۰).", reply_markup=await invite_settings_menu())


@router.callback_query(F.data == "adm_edit_invite_text")
async def cb_edit_invite_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("text_invite") or ""
    await state.set_state(AdminState.edit_invite_text)
    text = (
        "📝 <b>متن زیرمجموعه گیری</b>\n\n"
        "م فعلی:\n"
    )
    if current:
        text += f"<code>{current[:500]}</code>\n\n"
    else:
        text += "(متن پیش‌فرض)\n\n"
    text += (
        "متن جدید را ارسال کنید.\n"
        "متغیرها: <code>{link}</code> <code>{count}</code> <code>{reward}</code> <code>{symbol}</code>\n\n"
        "برای بازگشت به متن پیش‌فرض، بنویسید: <code>پیش‌فرض</code>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_invite_text)
async def process_edit_invite_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    value = "" if message.text.strip() == "پیش‌فرض" else message.text
    await set_setting("text_invite", value)
    await state.clear()
    await message.answer("✅ متن زیرمجموعه گیری به‌روزرسانی شد!", reply_markup=await invite_settings_menu())

@router.callback_query(F.data == "adm_edit_invite_reward_type")
async def cb_edit_invite_reward_type(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("invite_reward_type") or "fixed"
    await state.set_state(AdminState.edit_invite_reward_type)
    text = (
        "🎯 <b>نوع پاداش زیرمجموعه</b>\n\n"
        f"وضعیت فعلی: <b>{'پاداش ثابت' if current == 'fixed' else 'کمیسیون درصدی'}</b>\n\n"
        "نوع جدید را انتخاب کنید:"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 پاداش ثابت", callback_data="set_invite_type_fixed")],
        [InlineKeyboardButton(text="📊 کمیسیون درصدی", callback_data="set_invite_type_commission")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_edit_invite")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("set_invite_type_"))
async def cb_set_invite_type(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    reward_type = callback.data.replace("set_invite_type_", "")
    await set_setting("invite_reward_type", reward_type)
    type_label = "پاداش ثابت" if reward_type == "fixed" else "کمیسیون درصدی"
    await callback.answer(f"✅ نوع پاداش: {type_label}", show_alert=True)
    await callback.message.edit_text("✅ نوع پاداش به‌روزرسانی شد!", reply_markup=await invite_settings_menu())


@router.callback_query(F.data == "adm_edit_invite_commission")
async def cb_edit_invite_commission(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("invite_commission_percent") or "10"
    await state.set_state(AdminState.edit_invite_commission)
    await callback.message.edit_text(
        f"📊 <b>درصد کمیسیون</b>\n\n"
        f"درصد فعلی: <b>{current}%</b>\n\n"
        "درصد جدید را ارسال کنید (عدد بین ۱ تا ۱۰۰):",
        parse_mode="HTML",
        reply_markup=await invite_settings_menu()
    )


@router.message(AdminState.edit_invite_commission)
async def process_edit_invite_commission(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        pct = int(message.text.strip())
        if pct < 1 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً عددی بین ۱ تا ۱۰۰ وارد کنید:")
        return
    await set_setting("invite_commission_percent", str(pct))
    await state.clear()
    await message.answer(f"✅ درصد کمیسیون: {pct}%", reply_markup=await invite_settings_menu())


@router.callback_query(F.data == "adm_edit_currency")
async def cb_edit_currency(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.edit_currency)
    await callback.message.edit_text(
        f"💱 <b>نماد ارز</b>\n\nفعلی: <b>{current}</b>\n\nنماد جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_currency)
async def process_edit_currency(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("currency_symbol", message.text.strip())
    await state.clear()
    await message.answer("✅ نماد ارز به‌روزرسانی شد!", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_edit_cashback")
async def cb_edit_cashback(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("cashback_percent") or "0"
    await state.set_state(AdminState.edit_cashback_percent)
    await callback.message.edit_text(
        f"💰 <b>درصد کش‌بک</b>\n\n"
        f"فعلی: <b>{current}%</b>\n\n"
        f"درصد کش‌بک را وارد کنید (۰ = غیرفعال):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_cashback_percent)
async def process_cashback_percent(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        pct = float(message.text.strip())
        if pct < 0 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. درصدی بین ۰ تا ۱۰۰ وارد کنید:")
        return
    await set_setting("cashback_percent", str(pct))
    await state.clear()
    if pct > 0:
        await message.answer(f"✅ درصد کش‌بک: <b>{pct}%</b>", parse_mode="HTML", reply_markup=await settings_menu())
    else:
        await message.answer("✅ کش‌بک غیرفعال شد.", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_toggle_phone_verification")
async def cb_toggle_phone_verification(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("phone_verification_enabled") or "0"
    new_val = "0" if current == "1" else "1"
    await set_setting("phone_verification_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"تایید شماره تلفن {status}", show_alert=True)
    await callback.message.edit_text("⚙️ <b>تنظیمات ربات</b>", parse_mode="HTML", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_toggle_service_monitor")
async def cb_toggle_service_monitor(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("service_monitor_enabled") or "0"
    new_val = "0" if current == "1" else "1"
    await set_setting("service_monitor_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"مانیتور سرویس {status}", show_alert=True)
    await callback.message.edit_text("⚙️ <b>تنظیمات ربات</b>", parse_mode="HTML", reply_markup=await settings_menu())


@router.callback_query(F.data == "adm_toggle_expiry_reminder")
async def cb_toggle_expiry_reminder(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("expiry_reminder_enabled") or "1"
    new_val = "0" if current == "1" else "1"
    await set_setting("expiry_reminder_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"یادآوری انقضا {status}", show_alert=True)


@router.callback_query(F.data == "adm_qr_bg_info")
async def cb_qr_bg_info(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    import os
    bg_exists = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils", "qr_bg.png"))
    status = "✅ تصویر فعلی وجود دارد" if bg_exists else "❌ تصویری آپلود نشده"
    await callback.message.edit_text(
        f"📷 <b>پس‌زمینه QR Code</b>\n\n{status}\n\nبرای تغییر پس‌زمینه QR، از پنل وب استفاده کنید:\n"
        f"<code>http://212.87.199.33:5000/settings</code>",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


# ═══════════════════════════════════════════════════════════════
# Collaboration Settings
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_edit_collab")
async def cb_edit_collab(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🤝 <b>تنظیمات درخواست همکاری</b>", parse_mode="HTML", reply_markup=await collab_settings_menu())


@router.callback_query(F.data == "adm_toggle_collab")
async def cb_toggle_collab(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("collab_enabled") or "0"
    new_val = "0" if current == "1" else "1"
    await set_setting("collab_enabled", new_val)
    status = "فعال شد ✅" if new_val == "1" else "غیرفعال شد ❌"
    await callback.answer(f"درخواست همکاری {status}", show_alert=True)
    await callback.message.edit_text("🤝 <b>تنظیمات درخواست همکاری</b>", parse_mode="HTML", reply_markup=await collab_settings_menu())


@router.callback_query(F.data == "adm_edit_collab_channel")
async def cb_edit_collab_channel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("collab_notification_channel") or ""
    await state.set_state(AdminState.edit_collab_channel)
    await callback.message.edit_text(
        f"📢 <b>کانال اعلان درخواست همکاری</b>\n\n"
        f"فعلی: <code>{current if current else 'همان کانال اعلان اصلی'}</code>\n\n"
        f"شناسه کانال جدید را وارد کنید (مثلاً @mychannel یا -1001234567890):\n"
        f"برای استفاده از کانال اصلی، بنویسید: <code>-</code>",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_collab_channel)
async def process_edit_collab_channel(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text == "-":
        await set_setting("collab_notification_channel", "")
        await message.answer("✅ از کانال اصلی استفاده می‌شود.", reply_markup=await collab_settings_menu())
    else:
        await set_setting("collab_notification_channel", text)
        await message.answer(f"✅ کانال اعلان: <code>{text}</code>", parse_mode="HTML", reply_markup=await collab_settings_menu())
    await state.clear()


@router.callback_query(F.data == "adm_edit_collab_btn_text")
async def cb_edit_collab_btn_text(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("btn_collab_request") or "🤝 درخواست همکاری"
    await state.set_state(AdminState.edit_collab_btn_text)
    await callback.message.edit_text(
        f"📝 <b>متن دکمه درخواست همکاری</b>\n\n"
        f"فعلی: <b>{current}</b>\n\n"
        f"متن جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.edit_collab_btn_text)
async def process_edit_collab_btn_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("btn_collab_request", message.text.strip())
    await state.clear()
    await message.answer("✅ متن دکمه به‌روزرسانی شد!", reply_markup=await collab_settings_menu())


@router.callback_query(F.data == "adm_collab_requests")
async def cb_collab_requests(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    requests = await get_pending_collab_requests()
    if not requests:
        await callback.message.edit_text(
            "📋 <b>درخواست‌های همکاری</b>\n\nهیچ درخواست در انتظاری وجود ندارد.",
            parse_mode="HTML", reply_markup=await collab_settings_menu()
        )
        return
    await callback.message.edit_text(
        f"📋 <b>درخواست‌های همکاری</b> ({len(requests)})",
        parse_mode="HTML", reply_markup=await collab_requests_list(requests)
    )


@router.callback_query(F.data.startswith("adm_collab_detail_"))
async def cb_collab_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    request_id = int(callback.data.split("_")[-1])
    request = await get_collab_request(request_id)
    if not request:
        await callback.answer("❌ درخواست یافت نشد!", show_alert=True)
        return
    uname = f"@{request.get('username', 'ندارد')}" if request.get("username") else str(request["user_id"])
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🤝 <b>درخواست همکاری #{request['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👤 کاربر: {uname} (ID: <code>{request['user_id']}</code>)\n"
        f"  📛 نام: {request.get('first_name', 'ندارد')}\n"
        f"  📅 تاریخ: {request.get('created_at', '?')[:16]}\n"
        f"  📌 وضعیت: <b>{request['status']}</b>\n\n"
        f"  💬 پیام:\n{request['message']}"
    )
    if request["status"] == "pending":
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await collab_request_actions(request_id))
    else:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("collab_approve_"))
async def cb_collab_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    request_id = int(callback.data.split("_")[-1])
    request = await get_collab_request(request_id)
    if not request:
        await callback.answer("❌ درخواست یافت نشد!", show_alert=True)
        return
    if request["status"] != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده!", show_alert=True)
        return

    await update_collab_request(request_id, "approved", callback.from_user.id)
    await set_user_collaborator(request["user_id"], True)

    try:
        await callback.bot.send_message(
            chat_id=request["user_id"],
            text="✅ <b>درخواست همکاری شما تایید شد!</b>\n\nاکنون شما یک همکار هستید و از قیمت‌های ویژه بهره‌مند می‌شوید.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.answer("✅ درخواست تایید شد!", show_alert=True)
    requests = await get_pending_collab_requests()
    if requests:
        await callback.message.edit_text(
            f"📋 <b>درخواست‌های همکاری</b> ({len(requests)})",
            parse_mode="HTML", reply_markup=await collab_requests_list(requests)
        )
    else:
        await callback.message.edit_text(
            "📋 <b>درخواست‌های همکاری</b>\n\nهیچ درخواست در انتظاری وجود ندارد.",
            parse_mode="HTML", reply_markup=await collab_settings_menu()
        )


@router.callback_query(F.data.startswith("collab_reject_"))
async def cb_collab_reject(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    request_id = int(callback.data.split("_")[-1])
    request = await get_collab_request(request_id)
    if not request:
        await callback.answer("❌ درخواست یافت نشد!", show_alert=True)
        return
    if request["status"] != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده!", show_alert=True)
        return

    await state.update_data(collab_reject_request_id=request_id)
    await state.set_state(AdminState.collab_reject_reason)
    await callback.message.edit_text(
        f"❌ <b>رد درخواست همکاری</b>\n\n"
        f"دلیل رد را وارد کنید (این پیام برای کاربر ارسال خواهد شد):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )
    await callback.answer()


@router.message(AdminState.collab_reject_reason)
async def process_collab_reject_reason(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    request_id = data.get("collab_reject_request_id")
    request = await get_collab_request(request_id)
    if not request:
        await state.clear()
        await message.answer("❌ درخواست یافت نشد.", reply_markup=await back_to_admin())
        return

    await update_collab_request(request_id, "rejected", message.from_user.id)

    try:
        await message.bot.send_message(
            chat_id=request["user_id"],
            text=f"❌ <b>درخواست همکاری شما رد شد</b>\n\n"
                 f"📌 دلیل: {message.text.strip()}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await state.clear()
    await message.answer("✅ درخواست رد شد و به کاربر اطلاع داده شد.", reply_markup=await collab_settings_menu())


@router.callback_query(F.data.startswith("collab_reply_"))
async def cb_collab_reply(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    request_id = int(callback.data.split("_")[-1])
    request = await get_collab_request(request_id)
    if not request:
        await callback.answer("❌ درخواست یافت نشد!", show_alert=True)
        return
    await state.update_data(collab_reply_request_id=request_id)
    await state.set_state(AdminState.collab_reply_text)
    await callback.message.edit_text(
        "💬 <b>پاسخ به کاربر</b>\n\n"
        f"کاربر: @{request.get('username', 'ندارد')} (ID: {request['user_id']})\n"
        f"پیام اولیه:\n{request.get('message', '')}\n\n"
        "لطفاً پاسخ خود را ارسال کنید:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"collab_view_{request_id}")]
        ])
    )
    await callback.answer()


@router.message(AdminState.collab_reply_text)
async def process_collab_reply(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    request_id = data.get("collab_reply_request_id")
    request = await get_collab_request(request_id)
    if not request:
        await state.clear()
        await message.answer("❌ درخواست یافت نشد!", reply_markup=await collab_settings_menu())
        return
    try:
        await message.bot.send_message(
            chat_id=request["user_id"],
            text=f"💬 <b>پاسخ مدیر به درخواست همکاری:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("✅ پاسخ ارسال شد!", reply_markup=await collab_settings_menu())
    except Exception:
        await message.answer("❌ خطا در ارسال پاسخ به کاربر.", reply_markup=await collab_settings_menu())
    await state.clear()


@router.callback_query(F.data == "adm_control")
async def cb_control(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎛️ <b>کنترل‌پنل</b>", parse_mode="HTML", reply_markup=await control_panel_menu())


@router.callback_query(F.data == "cb_force_check_services")
async def cb_force_check_services(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer("🔍 در حال بررسی سرویس‌ها...", show_alert=True)
    from utils.service_monitor import check_services
    await check_services()
    await callback.message.edit_text("✅ <b>بررسی سرویس‌ها انجام شد.</b>", parse_mode="HTML", reply_markup=await control_panel_menu())


@router.callback_query(F.data == "adm_server_status")
async def cb_server_status(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from utils.server_status import get_server_status, format_server_status
    status = get_server_status()
    text = format_server_status(status)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await control_panel_menu())


@router.callback_query(F.data == "adm_toggle_mode")
async def cb_toggle_mode(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("operating_mode") or "NORMAL"
    cycle = {"NORMAL": "SALES_PAUSED", "SALES_PAUSED": "MAINTENANCE", "MAINTENANCE": "NORMAL"}
    new_mode = cycle.get(current, "NORMAL")
    await set_setting("operating_mode", new_mode)
    mode_labels = {"NORMAL": "🟢 عادی", "SALES_PAUSED": "🟡 فروش متوقف", "MAINTENANCE": "🔴 تعمیرات"}
    await callback.answer(f"حالت: {mode_labels.get(new_mode, new_mode)}", show_alert=True)
    from keyboards.admin import control_panel_menu
    await callback.message.edit_text(
        f"🎛️ <b>کنترل‌پنل</b>\n\nوضعیت فعلی: <b>{mode_labels.get(new_mode, new_mode)}</b>",
        parse_mode="HTML", reply_markup=await control_panel_menu(),
    )


@router.callback_query(F.data == "adm_test_connection_ctrl")
async def cb_test_connection_ctrl(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await cb_test_panel(callback)


@router.callback_query(F.data == "adm_restart_bot")
async def cb_restart_bot(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله، ری‌استارت", callback_data="adm_confirm_restart"),
            InlineKeyboardButton(text="❌ انصراف", callback_data="adm_control"),
        ],
    ])
    await callback.message.edit_text("🔄 <b>ری‌استارت ربات</b>\n\nآیا مطمئن هستید؟", parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "adm_confirm_restart")
async def cb_confirm_restart(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer("🔄 ربات در حال ری‌استارت...", show_alert=True)
    import subprocess
    try:
        subprocess.Popen(
            ["pm2", "restart", "nikeli-api"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


@router.callback_query(F.data == "adm_create_backup")
async def cb_create_backup(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    import tarfile, io, json, os
    from datetime import datetime
    from aiogram.types import FSInputFile

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(backup_dir, f"backup_{ts}.tar.gz")
    db_path = os.getenv("DB_PATH", "bot_database.db")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    manifest = {"created_at": datetime.now().isoformat(), "version": "1.0"}
    with tarfile.open(archive_path, "w:gz") as tar:
        if os.path.exists(db_path):
            tar.add(db_path, arcname="bot_database.db")
        if os.path.exists(env_path):
            tar.add(env_path, arcname=".env")
        info = tarfile.TarInfo(name="backup_manifest.json")
        data = json.dumps(manifest, indent=2).encode()
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    try:
        await callback.message.answer_document(
            document=FSInputFile(archive_path, filename=f"backup_{ts}.tar.gz"),
            caption=f"💾 <b>بکاپ ایجاد شد</b>\n\n📅 {ts}\n📦 {os.path.getsize(archive_path) / 1024:.1f} KB",
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.answer(f"❌ خطا: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data == "adm_backups_list")
async def cb_backups_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    import os
    from datetime import datetime
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    backups = []
    if os.path.exists(backup_dir):
        for fname in sorted(os.listdir(backup_dir), reverse=True):
            if fname.endswith(".tar.gz"):
                fpath = os.path.join(backup_dir, fname)
                stat = os.stat(fpath)
                size = stat.st_size
                if size < 1024:
                    size_str = f"{size} B"
                else:
                    size_str = f"{size / 1024:.1f} KB"
                backups.append({"name": fname, "size": size_str, "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")})
    if not backups:
        await callback.message.edit_text("📥 <b>بکاپ‌های موجود</b>\n\nهیچ بکاپی وجود ندارد.", parse_mode="HTML", reply_markup=await back_to_admin())
        return
    await callback.message.edit_text("📥 <b>بکاپ‌های موجود</b>", parse_mode="HTML", reply_markup=await backup_list_keyboard(backups))


# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# SECTION 9: Broadcast
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.broadcast_destination)
    await callback.message.edit_text(
        "📢 <b>ارسال همگانی</b>\n\n"
        "پیام را به کجا ارسال کنید؟",
        parse_mode="HTML", reply_markup=await broadcast_destination_keyboard()
    )


@router.callback_query(F.data.startswith("broadcast_dest_"))
async def cb_broadcast_destination(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    dest = callback.data.replace("broadcast_dest_", "")
    await state.update_data(broadcast_dest=dest)
    await state.set_state(AdminState.broadcast_text)
    user_count = await get_user_count()
    dest_labels = {"users": "کاربران", "channel": "کانال", "both": "کاربران و کانال"}
    await callback.message.edit_text(
        f"📢 <b>ارسال به {dest_labels.get(dest, dest)}</b>\n\n"
        f"👥 تعداد کل کاربران: <b>{user_count}</b>\n\n"
        f"پیام خود را ارسال کنید.\nاز HTML استفاده کنید: <b>بولد</b> — <i>ایتالیک</i> — <code>کد</code>",
        parse_mode="HTML", reply_markup=await broadcast_menu()
    )


@router.message(AdminState.broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_text=message.html_text or message.text)
    await state.set_state(AdminState.broadcast_button)
    await message.answer(
        "🔘 <b>انتخاب دکمه</b>\n\n"
        "دکمه مورد نظر را برای پیام انتخاب کنید:",
        parse_mode="HTML", reply_markup=await broadcast_button_keyboard()
    )


BROADCAST_BUTTON_MAP = {
    "broadcast_send_none": None,
    "broadcast_send_buy_config": {"text": "خرید کانفیگ", "callback": "buy_config", "emoji": "package", "btn_id": "buy_config"},
    "broadcast_send_wallet": {"text": "کیف پول", "callback": "wallet", "emoji": "wallet", "btn_id": "wallet"},
    "broadcast_send_free_test": {"text": "تست رایگان", "callback": "free_test", "emoji": "free_test", "btn_id": "free_test"},
    "broadcast_send_channel": {"text": "کانال ما", "url_setting": "channel_url", "emoji": "link", "btn_id": "channel"},
    "broadcast_send_support": {"text": "پشتیبانی", "url_setting": "support_url", "emoji": "owner", "btn_id": "support"},
}



# ─── Broadcast button with premium emoji support ──────────────
async def _broadcast_btn(text, callback_data, emoji_name, btn_id=None):
    from keyboards.user import _btn
    return await _btn(text, callback_data, emoji_name, btn_id=btn_id)


async def _broadcast_url_btn(text, url, emoji_name, btn_id=None):
    from aiogram.types import InlineKeyboardButton
    kwargs = {"text": text, "url": url}
    if btn_id:
        from database import get_setting
        db_emoji = await get_setting(f"btn_emoji_{btn_id}")
        if db_emoji:
            kwargs["icon_custom_emoji_id"] = db_emoji
        elif emoji_name:
            from utils.premium_emoji import get_button_emoji_id
            eid = await get_button_emoji_id(emoji_name)
            if eid:
                kwargs["icon_custom_emoji_id"] = eid
        db_style = await get_setting(f"btn_style_{btn_id}")
        if db_style:
            kwargs["style"] = db_style
    elif emoji_name:
        from utils.premium_emoji import get_button_emoji_id
        eid = await get_button_emoji_id(emoji_name)
        if eid:
            kwargs["icon_custom_emoji_id"] = eid
    return InlineKeyboardButton(**kwargs)

async def _do_broadcast(message: Message, bot, button_config=None, for_channel=False):
    users = await get_all_users()
    total = len(users)
    sent = 0
    failed = 0

    text = message.html_text if message.html_text else message.text

    reply_markup = None
    if button_config:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        btn_text = button_config["text"]
        emoji_name = button_config.get("emoji", None)
        btn_id = button_config.get("btn_id", None)
        if for_channel and "callback" in button_config:
            bot_username = (await bot.get_me()).username
            deep_link = f"https://t.me/{bot_username}?start={button_config['callback']}"
            btn = await _broadcast_url_btn(btn_text, deep_link, emoji_name, btn_id)
        elif "callback" in button_config:
            btn = await _broadcast_btn(btn_text, button_config["callback"], emoji_name, btn_id)
        elif "url_setting" in button_config:
            url = await get_setting(button_config["url_setting"]) or ""
            if not url:
                btn = None
            else:
                btn = await _broadcast_url_btn(btn_text, url, emoji_name, btn_id)
        else:
            btn = None
        if btn:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])

    if not for_channel:
        await message.answer(f"📢 در حال ارسال به {total} کاربر...")
    for user in users:
        try:
            await bot.send_message(
                chat_id=user["id"],
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            sent += 1
        except Exception:
            failed += 1
    return sent, failed, total



@router.callback_query(F.data.startswith("broadcast_pin_"))
async def cb_broadcast_pin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text", "")
    broadcast_dest = data.get("broadcast_dest", "users")
    button_data = data.get("broadcast_button_config", "")
    if not broadcast_text:
        await callback.answer("خطا: متن پیام یافت نشد!", show_alert=True)
        await state.clear()
        return

    pin_msg = callback.data == "broadcast_pin_yes"
    button_config = BROADCAST_BUTTON_MAP.get(button_data)
    await state.clear()

    class FakeMessage:
        def __init__(self, text, bot):
            self.html_text = text
            self.text = text
            self.bot = bot
            self._answer_text = None
        async def answer(self, text, **kwargs):
            self._answer_text = text
            return self

    fake_msg = FakeMessage(broadcast_text, callback.bot)

    sent_users = 0
    failed_users = 0
    total_users = 0
    sent_channel = 0

    if broadcast_dest in ("users", "both"):
        sent_users, failed_users, total_users = await _do_broadcast(fake_msg, callback.bot, button_config, for_channel=False)

    if broadcast_dest in ("channel", "both"):
        channel_id = await get_setting("required_channel_id") or ""
        if channel_id:
            text = broadcast_text
            reply_markup = None
            if button_config:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                btn_text = button_config["text"]
                emoji_name = button_config.get("emoji", None)
                btn_id_val = button_config.get("btn_id", None)
                if "callback" in button_config:
                    bot_username = (await callback.bot.get_me()).username
                    deep_link = f"https://t.me/{bot_username}?start={button_config['callback']}"
                    btn = await _broadcast_url_btn(btn_text, deep_link, emoji_name, btn_id_val)
                elif "url_setting" in button_config:
                    url = await get_setting(button_config["url_setting"]) or ""
                    if url:
                        btn = await _broadcast_url_btn(btn_text, url, emoji_name, btn_id_val)
                    else:
                        btn = None
                else:
                    btn = None
                if btn:
                    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])
            try:
                sent_msg = await callback.bot.send_message(
                    chat_id=channel_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                if pin_msg:
                    try:
                        await callback.bot.pin_chat_message(
                            chat_id=channel_id,
                            message_id=sent_msg.message_id,
                            disable_notification=False,
                        )
                    except Exception:
                        pass
                sent_channel = 1
            except Exception:
                sent_channel = 0

    btn_name = "ندارد"
    if button_config:
        btn_name = button_config["text"]

    dest_text = "کاربران"
    if broadcast_dest == "channel":
        dest_text = "کانال"
    elif broadcast_dest == "both":
        dest_text = "کاربران و کانال"

    result_text = f"📢 <b>ارسال همگانی تمام شد</b>\n\n"
    result_text += f"📍 مقصد: <b>{dest_text}</b>\n"
    result_text += f"🔘 دکمه: <b>{btn_name}</b>\n"
    result_text += f"📌 پین: <b>{'بله' if pin_msg else 'خیر'}</b>\n\n"
    if broadcast_dest in ("users", "both"):
        result_text += f"👥 کاربران: ✅ {sent_users} / ❌ {failed_users} / Σ {total_users}\n"
    if broadcast_dest in ("channel", "both"):
        result_text += f"📢 کانال: {'✅ ارسال شد' if sent_channel else '❌ خطا'}\n"
    result_text += "\n✅ <b>ارسال با موفقیت انجام شد!</b>"

    await callback.message.edit_text(result_text, parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("broadcast_send_"))
async def cb_broadcast_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text", "")
    broadcast_dest = data.get("broadcast_dest", "users")
    if not broadcast_text:
        await callback.answer("خطا: متن پیام یافت نشد!", show_alert=True)
        await state.clear()
        return

    button_config = BROADCAST_BUTTON_MAP.get(callback.data)
    await state.update_data(broadcast_button_config=callback.data)
    await state.set_state(AdminState.broadcast_pin)
    await callback.message.edit_text(
        "📌 <b>گزینه پین</b>\n\nآیا پیام در کانال پین شود؟",
        parse_mode="HTML", reply_markup=await broadcast_pin_keyboard()
    )



# SECTION 10: Menu Editor
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_menu_editor")
async def cb_menu_editor(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    import json
    raw = await get_setting("menu_layout") or "[]"
    try:
        layout = json.loads(raw)
    except Exception:
        layout = []
    LABELS = {
        "wallet": "💰 کیف پول", "free_test": "🧪 تست رایگان", "buy_config": "🛒 خرید کانفیگ",
        "my_configs": "📋 سرویس‌ها", "channel": "📢 کانال", "support": "💬 پشتیبانی",
        "admin": "⚙️ ادمین", "invite": "👥 زیرمجموعه", "collab": "🤝 همکاری",
        "guides": "📖 راهنماها", "tutorials": "🎓 آموزش اتصال",
        "redeem_gift": "🎁 کد هدیه", "webapp": "🌐 وب‌اپ",
    }
    summary = []
    for item in layout:
        if item.get("type") == "row_break":
            summary.append({"label": "── ردیف جدید ──", "enabled": True})
        elif item.get("type") == "custom":
            summary.append({"label": f"🔗 {item.get('text', 'سفارشی')}", "enabled": True})
        elif item.get("type") == "builtin":
            bid = item.get("id", "")
            summary.append({"label": LABELS.get(bid, bid), "enabled": item.get("enabled", True)})
    if layout and not any(i.get("type") == "builtin" and i.get("id") == "tutorials" for i in layout):
        from database import set_setting
        nl, placed = [], False
        for item in layout:
            nl.append(item)
            if item.get("type") == "builtin" and item.get("id") == "guides":
                nl.append({"type": "builtin", "id": "tutorials", "enabled": True})
                placed = True
        if not placed:
            ins = None
            for i, item in enumerate(nl):
                if item.get("type") == "builtin" and item.get("id") in ("support", "admin"):
                    ins = i
                    break
            if ins is None:
                nl.extend([{"type": "row_break"}, {"type": "builtin", "id": "tutorials", "enabled": True}])
            else:
                nl.insert(ins, {"type": "builtin", "id": "tutorials", "enabled": True})
                if ins > 0 and nl[ins - 1].get("type") != "row_break":
                    nl.insert(ins, {"type": "row_break"})
        layout = nl
        await set_setting("menu_layout", json.dumps(layout))
    await callback.message.edit_text("📱 <b>ویرایش منوی اصلی</b>", parse_mode="HTML", reply_markup=await menu_editor_menu(summary))


# ─── Discount Codes Management ─────────────────────────────────
@router.callback_query(F.data == "adm_discounts")
async def cb_adm_discounts(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    codes = await get_all_discount_codes()
    if not codes:
        text = "🏷️ <b>کدهای تخفیف</b>\n\nهنوز کد تخفیفی ایجاد نشده است."
    else:
        text = f"🏷️ <b>کدهای تخفیف</b> ({len(codes)})\n\nلیست کدهای تخفیف شما:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await discount_codes_menu(codes))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await discount_codes_menu(codes))


@router.callback_query(F.data == "adm_add_discount")
async def cb_adm_add_discount_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_discount_code)
    text = "🏷️ <b>ایجاد کد تخفیف جدید</b>\n\nکد تخفیف را وارد کنید (مثال: SUMMER30):"
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")


@router.message(AdminState.add_discount_code)
async def cb_adm_add_discount_code(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    code = (message.text or "").strip().upper()
    if not code or len(code) < 3:
        await message.answer("کد نامعتبر است. حداقل ۳ کاراکتر وارد کنید:")
        return
    existing = await get_discount_code(code)
    if existing:
        await message.answer("این کد قبلاً استفاده شده است. کد دیگری وارد کنید:")
        return
    await state.update_data(discount_code=code)
    await state.set_state(AdminState.add_discount_type)
    from keyboards.admin import _btn
    from aiogram.types import InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("📊 درصدی", "adm_dtype_percent", "link", btn_id="dtype_percent"),
         await _btn("💰 مبلغی", "adm_dtype_fixed", "link", btn_id="dtype_fixed")],
        [await _btn("لغو", "adm_discounts", btn_id="cancel")],
    ])
    await message.answer("نوع تخفیف را انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_dtype_"))
async def cb_adm_discount_type(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    dtype = "percent" if callback.data == "adm_dtype_percent" else "fixed"
    await state.update_data(discount_type=dtype)
    await state.set_state(AdminState.add_discount_value)
    label = "درصد" if dtype == "percent" else "مبلغ (تومان)"
    try:
        await callback.message.edit_text(f"مقدار تخفیف ({label}) را وارد کنید:")
    except Exception:
        await callback.message.answer(f"مقدار تخفیف ({label}) را وارد کنید:")


@router.message(AdminState.add_discount_value)
async def cb_adm_add_discount_value(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        value = float((message.text or "").strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید:")
        return
    data = await state.get_data()
    if data.get("discount_type") == "percent" and value > 100:
        await message.answer("درصد نمی‌تواند بیشتر از ۱۰۰ باشد:")
        return
    await state.update_data(discount_value=value)
    await state.set_state(AdminState.add_discount_max)
    await message.answer("حداکثر تعداد استفاده را وارد کنید (۰ = نامحدود):")


@router.message(AdminState.add_discount_max)
async def cb_adm_add_discount_max(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        max_uses = int((message.text or "").strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح وارد کنید:")
        return
    await state.update_data(discount_max_uses=max_uses)
    await state.set_state(AdminState.add_discount_expiry)
    await message.answer("مدت اعتبار (ساعت) را وارد کنید (۰ = بدون محدودیت زمانی):")


@router.message(AdminState.add_discount_expiry)
async def cb_adm_add_discount_expiry(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        hours = int((message.text or "").strip())
        if hours < 0:
            raise ValueError
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح وارد کنید:")
        return
    expires_at = None
    if hours > 0:
        from datetime import datetime, timedelta
        expires_at = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    await state.update_data(discount_expires_at=expires_at)
    await state.set_state(AdminState.add_discount_plan)
    from keyboards.admin import _btn
    from aiogram.types import InlineKeyboardMarkup
    plans = await get_all_plans()
    buttons = []
    buttons.append([await _btn("همه پلن‌ها", "adm_dplan_0", "link", btn_id="dplan_all")])
    for p in plans[:10]:
        buttons.append([await _btn(p["name"], f"adm_dplan_{p['id']}", "link", btn_id="dplan_item")])
    buttons.append([await _btn("لغو", "adm_discounts", btn_id="cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("پلن مورد نظر را انتخاب کنید (یا همه پلن‌ها):", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_dplan_"))
async def cb_adm_discount_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    plan_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    code = data.get("discount_code", "")
    dtype = data.get("discount_type", "percent")
    value = data.get("discount_value", 0)
    max_uses = data.get("discount_max_uses", 0)
    expires_at = data.get("discount_expires_at")

    code_id = await add_discount_code(code, dtype, value, max_uses, expires_at, plan_id)
    await state.clear()

    type_label = "درصد" if dtype == "percent" else "تومان"
    plan_label = "همه پلن‌ها" if plan_id == 0 else f"پلن #{plan_id}"
    expiry_label = expires_at[:16] if expires_at else "نامحدود"
    max_label = str(max_uses) if max_uses > 0 else "نامحدود"

    text = (
        f"✅ <b>کد تخفیف ایجاد شد!</b>\n\n"
        f"  🏷️ کد: <code>{code}</code>\n"
        f"  📊 نوع: {type_label}\n"
        f"  💰 مقدار: {value}{type_label}\n"
        f"  🔢 حداکثر استفاده: {max_label}\n"
        f"  📅 انقضا: {expiry_label}\n"
        f"  📦 پلن: {plan_label}"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_admin())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("adm_discount_detail_"))
async def cb_adm_discount_detail(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    code_id = int(callback.data.split("_")[-1])
    code = await get_discount_code_by_id(code_id)
    if not code:
        await callback.answer("کد یافت نشد!", show_alert=True)
        return
    type_label = "درصد" if code["discount_type"] == "percent" else "تومان"
    plan_label = "همه پلن‌ها" if code["plan_id"] == 0 else f"پلن #{code['plan_id']}"
    expiry_label = code["expires_at"][:16] if code["expires_at"] else "نامحدود"
    max_label = str(code["max_uses"]) if code["max_uses"] > 0 else "نامحدود"
    status = "🟢 فعال" if code["is_active"] else "🔴 غیرفعال"

    text = (
        f"🏷️ <b>جزئیات کد تخفیف</b>\n\n"
        f"  🏷️ کد: <code>{code['code']}</code>\n"
        f"  📊 وضعیت: {status}\n"
        f"  📊 نوع: {type_label}\n"
        f"  💰 مقدار: {code['discount_value']}{type_label}\n"
        f"  🔢 استفاده شده: {code['used_count']}/{max_label}\n"
        f"  📅 انقضا: {expiry_label}\n"
        f"  📦 پلن: {plan_label}"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await discount_code_detail_menu(code_id, code["is_active"]))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await discount_code_detail_menu(code_id, code["is_active"]))


@router.callback_query(F.data.startswith("adm_delete_discount_"))
async def cb_adm_delete_discount(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    code_id = int(callback.data.split("_")[-1])
    await delete_discount_code(code_id)
    await callback.answer("کد حذف شد!", show_alert=True)
    codes = await get_all_discount_codes()
    text = "🏷️ <b>کدهای تخفیف</b>\n\nکد با موفقیت حذف شد."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await discount_codes_menu(codes))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await discount_codes_menu(codes))


# ═══════════════════════════════════════════════════════════════
# SECTION: Blacklist Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_blacklist")
async def cb_blacklist(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    users = await get_blacklisted_users()
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "  ⛔ <b>لیست سیاه (Blacklist)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👥 تعداد مسدود شده: <b>{len(users)}</b>\n"
    )
    if not users:
        text += "\n  هیچ کاربری مسدود نشده است."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await blacklist_keyboard(users))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await blacklist_keyboard(users))


@router.callback_query(F.data == "adm_blacklist_add")
async def cb_blacklist_add(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.blacklist_add_id)
    await callback.message.edit_text(
        "⛔ <b>مسدود کردن کاربر</b>\n\nآیدی عددی کاربر را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.blacklist_add_id)
async def process_blacklist_add_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ آیدی نامعتبر. یک عدد وارد کنید:")
        return
    user = await get_user(user_id)
    if not user:
        await message.answer("❌ کاربر یافت نشد.", reply_markup=await back_to_admin())
        return
    await state.update_data(blacklist_target=user_id)
    await state.set_state(AdminState.blacklist_add_reason)
    uname = f"@{user.get('username', 'ندارد')}" if user.get("username") else str(user_id)
    await message.answer(
        f"👤 کاربر: {uname} (<code>{user_id}</code>)\n\n"
        f"📝 دلیل مسدودی را وارد کنید (اختیاری، برای رد کردن بنویسید <code>-</code>):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.blacklist_add_reason)
async def process_blacklist_add_reason(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get("blacklist_target")
    reason = "" if message.text.strip() == "-" else message.text.strip()
    await add_to_blacklist(user_id, reason)
    await state.clear()
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text="⛔ شما از استفاده از ربات محروم شده‌اید.",
        )
    except Exception:
        pass
    await message.answer(
        f"✅ کاربر <code>{user_id}</code> مسدود شد.",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


# ═══════════════════════════════════════════════════════════════
# SECTION: Gift Codes Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_gift_codes")
async def cb_gift_codes(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    codes = await get_all_gift_codes()
    if not codes:
        text = "🎁 <b>کدهای هدیه</b>\n\nهنوز کد هدیه‌ای ایجاد نشده است."
    else:
        text = f"🎁 <b>کدهای هدیه</b> ({len(codes)})\n\nلیست کدهای هدیه شما:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await gift_codes_menu(codes))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await gift_codes_menu(codes))


@router.callback_query(F.data == "adm_add_gift_code")
async def cb_add_gift_code_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.gift_code_code)
    await callback.message.edit_text(
        "🎁 <b>ایجاد کد هدیه جدید</b>\n\nکد هدیه را وارد کنید (مثال: GIFT100):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.gift_code_code)
async def process_gift_code_code(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    code = (message.text or "").strip().upper()
    if not code or len(code) < 3:
        await message.answer("کد نامعتبر است. حداقل ۳ کاراکتر وارد کنید:")
        return
    await state.update_data(gift_code=code)
    symbol = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.gift_code_amount)
    await message.answer(f"💰 مبلغ هدیه را به {symbol} وارد کنید:")


@router.message(AdminState.gift_code_amount)
async def process_gift_code_amount(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(gift_amount=amount)
    await state.set_state(AdminState.gift_code_max_uses)
    await message.answer("حداکثر تعداد استفاده را وارد کنید (۰ = نامحدود):")


@router.message(AdminState.gift_code_max_uses)
async def process_gift_code_max_uses(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("لطفاً یک عدد صحیح وارد کنید:")
        return

    data = await state.get_data()
    code = data["gift_code"]
    amount = data["gift_amount"]

    await add_gift_code(code, amount, max_uses)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    max_label = str(max_uses) if max_uses > 0 else "نامحدود"
    text = (
        f"✅ <b>کد هدیه ایجاد شد!</b>\n\n"
        f"  🎁 کد: <code>{code}</code>\n"
        f"  💰 مبلغ: {amount:,.0f} {symbol}\n"
        f"  🔢 حداکثر استفاده: {max_label}"
    )
    try:
        await message.answer(text, parse_mode="HTML", reply_markup=await back_to_admin())
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("adm_gift_detail_"))
async def cb_gift_detail(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    code_id = int(callback.data.split("_")[-1])
    code = await get_gift_code_by_id(code_id)
    if not code:
        await callback.answer("کد یافت نشد!", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    status = "🟢 فعال" if code["active"] else "🔴 غیرفعال"
    max_label = str(code["max_uses"]) if code["max_uses"] > 0 else "نامحدود"
    text = (
        f"🎁 <b>جزئیات کد هدیه</b>\n\n"
        f"  🎁 کد: <code>{code['code']}</code>\n"
        f"  📌 وضعیت: {status}\n"
        f"  💰 مبلغ: {code['amount']:,.0f} {symbol}\n"
        f"  🔢 استفاده شده: {code['uses']}/{max_label}"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await gift_code_detail_menu(code_id, code["active"]))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await gift_code_detail_menu(code_id, code["active"]))


@router.callback_query(F.data.startswith("adm_delete_gift_code_"))
async def cb_delete_gift_code(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    code_id = int(callback.data.split("_")[-1])
    await delete_gift_code(code_id)
    await callback.answer("کد حذف شد!", show_alert=True)
    codes = await get_all_gift_codes()
    text = "🎁 <b>کدهای هدیه</b>\n\nکد با موفقیت حذف شد."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await gift_codes_menu(codes))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await gift_codes_menu(codes))


# ═══════════════════════════════════════════════════════════════
# SECTION: Guides Management
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_guides")
async def cb_guides(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "📖 <b>مدیریت راهنماها</b>\n\nپلتفرم مورد نظر را انتخاب کنید:",
        parse_mode="HTML", reply_markup=await guide_platforms_menu()
    )


@router.callback_query(F.data.startswith("adm_guide_platform_"))
async def cb_guide_platform_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    platform = callback.data.replace("adm_guide_platform_", "")
    guides = await get_all_guides()
    platform_guides = [g for g in guides if g["platform"] == platform]

    buttons = []
    for g in platform_guides[:10]:
        status = "🟢" if g["active"] else "🔴"
        label = g["body"][:40] if g["body"] else f"{g['media_type']} #{g['id']}"
        buttons.append([InlineKeyboardButton(
            text=f"{status} #{g['id']} — {label}",
            callback_data=f"adm_guide_item_{g['id']}",
        )])
    buttons.append([await _btn("➕ افزودن راهنما", f"adm_add_guide_{platform}", "plus", btn_id="add_guide")])
    buttons.append([await _btn("🔙 بازگشت", "adm_guides", btn_id="back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"📖 <b>راهنهای {platform}</b> ({len(platform_guides)})"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_add_guide_"))
async def cb_add_guide_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    platform = callback.data.replace("adm_add_guide_", "")
    await state.update_data(guide_platform=platform)
    await state.set_state(AdminState.guide_body)
    await callback.message.edit_text(
        f"📖 <b>افزودن راهنما برای {platform}</b>\n\n"
        f"متن راهنما را ارسال کنید (یا برای ارسال فایل، بنویسید <code>فایل</code>):",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.guide_body)
async def process_guide_body(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    platform = data["guide_platform"]

    if message.text and message.text.strip() == "فایل":
        await state.set_state(AdminState.guide_media)
        await message.answer(
            "📎 فایل (عکس، ویدیو، یا سند) را ارسال کنید:",
            reply_markup=await back_to_admin()
        )
        return

    body = message.html_text if message.html_text else (message.text or "")
    if not body.strip():
        await message.answer("متن نمی‌تواند خالی باشد:")
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "PHOTO"
    elif message.video:
        file_id = message.video.file_id
        media_type = "VIDEO"
    elif message.document:
        file_id = message.document.file_id
        media_type = "DOCUMENT"
    else:
        file_id = ""
        media_type = "TEXT"

    await add_guide_item(platform, media_type, body, file_id)
    await state.clear()
    await message.answer(
        f"✅ راهنما برای {platform} اضافه شد!",
        reply_markup=await back_to_admin()
    )


@router.message(AdminState.guide_media)
async def process_guide_media(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    platform = data["guide_platform"]

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "PHOTO"
    elif message.video:
        file_id = message.video.file_id
        media_type = "VIDEO"
    elif message.document:
        file_id = message.document.file_id
        media_type = "DOCUMENT"
    else:
        await message.answer("لطفاً یک فایل (عکس، ویدیو، یا سند) ارسال کنید:")
        return

    body = message.caption or ""
    await add_guide_item(platform, media_type, body, file_id)
    await state.clear()
    await message.answer(
        f"✅ راهنما برای {platform} اضافه شد!",
        reply_markup=await back_to_admin()
    )


@router.callback_query(F.data.startswith("adm_guide_item_"))
async def cb_guide_item_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    guide_id = int(callback.data.split("_")[-1])
    from database import get_db
    db = await get_db()
    cursor = await db.execute("SELECT * FROM guide_items WHERE id = ?", (guide_id,))
    row = await cursor.fetchone()
    await db.close()
    if not row:
        await callback.answer("راهنما یافت نشد!", show_alert=True)
        return
    guide = dict(row)
    status = "🟢 فعال" if guide["active"] else "🔴 غیرفعال"
    body_preview = (guide.get("body") or "")[:100]
    text = (
        f"📖 <b>راهنما #{guide['id']}</b>\n\n"
        f"  📌 وضعیت: {status}\n"
        f"  📱 پلتفرم: {guide['platform']}\n"
        f"  📎 نوع: {guide['media_type']}\n"
        f"  💬 متن: {body_preview or '(خالی)'}"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ حذف", callback_data=f"adm_delete_guide_{guide_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_guide_platform_{guide['platform']}")],
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("adm_delete_guide_"))
async def cb_delete_guide(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    guide_id = int(callback.data.split("_")[-1])
    from database import get_db
    db = await get_db()
    cursor = await db.execute("SELECT platform FROM guide_items WHERE id = ?", (guide_id,))
    row = await cursor.fetchone()
    await db.close()
    platform = dict(row)["platform"] if row else "android"
    await delete_guide_item(guide_id)
    await callback.answer("راهنما حذف شد!", show_alert=True)
    await callback.message.edit_text(
        f"📖 <b>مدیریت راهنماها</b>",
        parse_mode="HTML", reply_markup=await guide_platforms_menu()
    )


# ═══════════════════════════════════════════════════════════════
# SECTION: Support Message Reply (Admin)
# ═══════════════════════════════════════════════════════════════
@router.message(F.reply_to_message)
async def handle_admin_support_reply(message: Message):
    if not await is_admin(message.from_user.id):
        return
    if not message.reply_to_message:
        return

    user_id = await get_support_user(message.reply_to_message.message_id)
    if not user_id:
        return

    try:
        if message.text:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"💬 <b>پاسخ پشتیبانی:</b>\n\n{message.text}",
                parse_mode="HTML",
            )
        elif message.photo:
            await message.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=f"💬 <b>پاسخ پشتیبانی:</b>\n\n{message.caption or ''}",
                parse_mode="HTML",
            )
        elif message.document:
            await message.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=f"💬 <b>پاسخ پشتیبانی:</b>\n\n{message.caption or ''}",
                parse_mode="HTML",
            )
        else:
            await message.bot.send_message(
                chat_id=user_id,
                text="💬 <b>پاسخ پشتیبانی:</b>\n\n[Unsupported message type]",
                parse_mode="HTML",
            )
        await message.answer("✅ پاسخ ارسال شد.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to forward support reply: %s %s", type(e).__name__, e)
        await message.answer("❌ خطا در ارسال پاسخ.")


@router.callback_query(F.data.startswith("adm_blacklist_detail_"))
async def cb_blacklist_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    user = await get_user(user_id)
    uname = f"@{user.get('username', 'ندارد')}" if user else str(user_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 رفع مسدودی", callback_data=f"adm_blacklist_remove_{user_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_blacklist")],
    ])
    await callback.message.edit_text(
        f"⛔ <b>کاربر مسدود شده</b>\n\n"
        f"  👤 کاربر: {uname}\n"
        f"  🔢 آیدی: <code>{user_id}</code>",
        parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data.startswith("adm_blacklist_remove_"))
async def cb_blacklist_remove(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split("_")[-1])
    await remove_from_blacklist(user_id)
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text="✅ مسدودی شما رفع شد. اکنون می‌توانید از ربات استفاده کنید.",
        )
    except Exception:
        pass
    await callback.answer("✅ کاربر از لیست سیاه خارج شد!", show_alert=True)
    users = await get_blacklisted_users()
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "  ⛔ <b>لیست سیاه (Blacklist)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👥 تعداد مسدود شده: <b>{len(users)}</b>\n"
    )
    if not users:
        text += "\n  هیچ کاربری مسدود نشده است."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await blacklist_keyboard(users))


@router.message(Command("save"))
async def cmd_save(message: Message):
    if not await is_admin(message.from_user.id):
        return
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] == 'ok':
            await message.answer("✅ Database integrity OK.\n💾 All data saved successfully.")
        else:
            await message.answer(f"⚠️ Database integrity issue: {result[0]}")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.message(Command("dbstatus"))
async def cmd_dbstatus(message: Message):
    if not await is_admin(message.from_user.id):
        return
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
    size = os.path.getsize(db_path)
    conn = sqlite3.connect(db_path)
    tables = ['users', 'plans', 'configs', 'receipts', 'panels', 'blacklist']
    lines = [f"📊 <b>Database Status</b>\n📦 Size: {size:,} bytes\n"]
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            lines.append(f"  {t}: {count} rows")
        except Exception:
            lines.append(f"  {t}: N/A")
    conn.close()
    await message.answer("\n".join(lines), parse_mode="HTML")


# ==================== Tutorial Admin Handlers ====================

@router.callback_query(F.data == "adm_tutorials")
async def cb_adm_tutorials(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎓 <b>مدیریت آموزش‌ها</b>\n\nآموزش مورد نظر را انتخاب کنید یا آموزش جدید اضافه کنید:",
        parse_mode="HTML", reply_markup=await tutorials_menu()
    )


@router.callback_query(F.data.startswith("adm_tut_detail_"))
async def cb_adm_tut_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    tut = await get_tutorial(tut_id)
    if not tut:
        await callback.answer("آموزش یافت نشد!", show_alert=True)
        return
    items = await get_tutorial_items(tut_id)
    status = "🟢 فعال" if tut["is_enabled"] else "🔴 غیرفعال"
    text = (
        f"🎓 <b>{tut['title']}</b>\n"
        f"وضعیت: {status}\n"
        f"تعداد زیرمجموعه‌ها: {len(items)}\n\n"
        f"زیرمجموعه‌ها:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await tutorial_detail_menu(tut_id))


@router.callback_query(F.data == "adm_add_tutorial")
async def cb_adm_add_tutorial(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.tutorial_title)
    await callback.message.edit_text(
        "🎓 <b>افزودن آموزش جدید</b>\n\nعنوان آموزش را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.tutorial_title)
async def process_tutorial_title(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد:")
        return
    tut_id = await add_tutorial(title)
    await state.clear()
    await message.answer(
        f"✅ آموزش «{title}» ایجاد شد!\nحالا زیرمجموعه‌ها را اضافه کنید.",
        reply_markup=await tutorial_detail_menu(tut_id)
    )


@router.callback_query(F.data.startswith("adm_edit_tutorial_"))
async def cb_adm_edit_tutorial(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_tutorial_id=tut_id)
    await state.set_state(AdminState.tutorial_edit_title)
    tut = await get_tutorial(tut_id)
    await callback.message.edit_text(
        f"✏️ <b>ویرایش عنوان</b>\n\nعنوان فعلی: {tut['title']}\n\nعنوان جدید را وارد کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.tutorial_edit_title)
async def process_tutorial_edit_title(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tut_id = data.get("edit_tutorial_id")
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد:")
        return
    await update_tutorial(tut_id, title=title)
    await state.clear()
    await message.answer(
        f"✅ عنوان به «{title}» تغییر کرد.",
        reply_markup=await tutorial_detail_menu(tut_id)
    )


@router.callback_query(F.data.startswith("adm_toggle_tutorial_"))
async def cb_adm_toggle_tutorial(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    await toggle_tutorial(tut_id)
    tut = await get_tutorial(tut_id)
    status = "فعال" if tut["is_enabled"] else "غیرفعال"
    await callback.answer(f"آموزش {status} شد", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=await tutorial_detail_menu(tut_id))


@router.callback_query(lambda c: c.data and c.data.startswith("adm_delete_tutorial_") and "_yes_" not in c.data)
async def cb_adm_delete_tutorial_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    tut = await get_tutorial(tut_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف شود", callback_data=f"adm_delete_tutorial_yes_{tut_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"adm_tut_detail_{tut_id}")],
    ])
    await callback.message.edit_text(
        f"⚠️ <b>آیا از حذف آموزش «{tut['title']}» مطمئنید؟</b>\n\nتمام زیرمجموعه‌ها نیز حذف خواهند شد.",
        parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data.startswith("adm_delete_tutorial_yes_"))
async def cb_adm_delete_tutorial_yes(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    await delete_tutorial(tut_id)
    await callback.answer("آموزش حذف شد", show_alert=True)
    await callback.message.edit_text(
        "🎓 <b>مدیریت آموزش‌ها</b>",
        parse_mode="HTML", reply_markup=await tutorials_menu()
    )


@router.callback_query(F.data.startswith("adm_add_tutitem_"))
async def cb_adm_add_tutitem(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    tut_id = int(callback.data.split("_")[-1])
    await state.update_data(tutitem_tutorial_id=tut_id)
    await state.set_state(AdminState.tutitem_title)
    await callback.message.edit_text(
        "📝 <b>افزودن زیرمجموعه</b>\n\nعنوان را به صورت متن ارسال کنید، یا برای افزودن سریع، عکس/ویدیو همراه با عنوان در کپشن بفرستید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.tutitem_title)
async def process_tutitem_title(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tut_id = data.get("tutitem_tutorial_id")

    m_photo = message.photo[-1].file_id if message.photo else None
    m_video = message.video.file_id if message.video else None
    m_anim = getattr(message, "animation", None)

    if m_photo or m_video or m_anim:
        if m_photo:
            ctype, fid = "PHOTO", m_photo
        elif m_video:
            ctype, fid = "VIDEO", m_video
        else:
            ctype, fid = "ANIMATION", m_anim.file_id
        cap = (message.caption or "").strip()
        if not cap:
            await state.update_data(pending_ctype=ctype, pending_fid=fid)
            await state.set_state(AdminState.tutitem_mediatitle)
            await message.answer(
                "\U0001F4DD <b>عنوان این دکمه را ارسال کنید</b>:",
                parse_mode="HTML", reply_markup=await back_to_admin()
            )
            return
        title = cap.split("\n")[0].strip()[:60]
        await add_tutorial_item(tut_id, title, ctype, cap, fid)
        await state.clear()
        await message.answer(
            f"✅ زیرمجموعه «{title}» اضافه شد!",
            reply_markup=await tutorial_detail_menu(tut_id)
        )
        return

    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد. متن بفرستید، یا عکس/ویدیو همراه با عنوان در کپشن ارسال کنید:")
        return
    await state.update_data(tutitem_title=title)
    await state.set_state(AdminState.tutitem_content)
    await message.answer(
        "📎 <b>محتوا را ارسال کنید</b>\n\nمتن، عکس، ویدیو یا گیف ارسال کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )
@router.message(AdminState.tutitem_content)
async def process_tutitem_content(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tut_id = data.get("tutitem_tutorial_id")
    title = data.get("tutitem_title", "")

    if message.photo:
        content_type = "PHOTO"
        content_file_id = message.photo[-1].file_id
        content_text = message.caption or ""
    elif message.video:
        content_type = "VIDEO"
        content_file_id = message.video.file_id
        content_text = message.caption or ""
    elif getattr(message, "animation", None):
        content_type = "ANIMATION"
        content_file_id = message.animation.file_id
        content_text = message.caption or ""
    elif message.text:
        content_type = "TEXT"
        content_file_id = ""
        content_text = message.html_text or message.text
    else:
        await message.answer("این نوع محتوا پشتیبانی نمی‌شود. متن، عکس، ویدیو یا گیف ارسال کنید:")
        return

    await add_tutorial_item(tut_id, title, content_type, content_text, content_file_id)
    await state.clear()
    await message.answer(
        f"✅ زیرمجموعه «{title}» اضافه شد!",
        reply_markup=await tutorial_detail_menu(tut_id)
    )


@router.callback_query(F.data.startswith("adm_tutitem_detail_"))
async def cb_adm_tutitem_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    item_id = int(callback.data.split("_")[-1])
    item = await get_tutorial_item(item_id)
    if not item:
        await callback.answer("زیرمجموعه یافت نشد!", show_alert=True)
        return
    ct_icons = {"TEXT": "📝", "PHOTO": "📷", "VIDEO": "🎬"}
    icon = ct_icons.get(item["content_type"], "📄")
    text = (
        f"{icon} <b>{item['title']}</b>\n\n"
        f"نوع: {item['content_type']}\n"
    )
    if item["content_text"]:
        text += f"متن: {item['content_text'][:200]}\n"
    if item["content_file_id"]:
        text += f"فایل: {item['content_file_id'][:30]}...\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await tutorial_item_detail_menu(item_id, item["tutorial_id"]))


@router.callback_query(F.data.startswith("adm_delete_tutitem_"))
async def cb_adm_delete_tutitem(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    item_id = int(callback.data.split("_")[-1])
    item = await get_tutorial_item(item_id)
    if not item:
        await callback.answer("یافت نشد!", show_alert=True)
        return
    await delete_tutorial_item(item_id)
    await callback.answer("زیرمجموعه حذف شد", show_alert=True)
    await callback.message.edit_text(
        "📝 زیرمجموعه حذف شد",
        reply_markup=await tutorial_detail_menu(item["tutorial_id"])
    )

@router.callback_query(F.data == "adm_toggle_mm_tutorials")
async def cb_adm_toggle_mm_tutorials(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    from database import set_setting
    cur = await get_setting("tutorials_enabled") or "0"
    await set_setting("tutorials_enabled", "0" if cur == "1" else "1")
    new_val = await get_setting("tutorials_enabled")
    status = "فعال" if new_val == "1" else "غیرفعال"
    await callback.answer(f"دکمه «آموزش اتصال» در منوی اصلی: {status}", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=await tutorials_menu())
    except Exception:
        pass

@router.callback_query(F.data.startswith("adm_menu_toggle_"))
async def cb_menu_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    import json
    from database import set_setting
    try:
        idx = int(callback.data.rsplit("_", 1)[1])
    except ValueError:
        await callback.answer()
        return
    raw = await get_setting("menu_layout") or "[]"
    try:
        layout = json.loads(raw)
    except Exception:
        layout = []
    if idx < 0 or idx >= len(layout):
        await callback.answer()
        return
    item = layout[idx]
    if item.get("type") == "row_break":
        await callback.answer("ردیف قابل تغییر نیست")
        return
    item["enabled"] = not item.get("enabled", True)
    await set_setting("menu_layout", json.dumps(layout))

    LABELS = {
        "wallet": "💰 کیف پول", "free_test": "🧪 تست رایگان", "buy_config": "🛒 خرید کانفیگ",
        "my_configs": "📋 سرویس‌ها", "channel": "📢 کانال", "support": "💬 پشتیبانی",
        "admin": "⚙️ ادمین", "invite": "👥 زیرمجموعه", "collab": "🤝 همکاری",
        "guides": "📖 راهنماها", "tutorials": "🎓 آموزش اتصال",
        "redeem_gift": "🎁 کد هدیه", "webapp": "🌐 وب\u200cاپ",
    }
    summary = []
    for it in layout:
        if it.get("type") == "row_break":
            summary.append({"label": "── ردیف جدید ──", "enabled": True})
        elif it.get("type") == "custom":
            summary.append({"label": f"🔗 {it.get('text', 'سفارشی')}", "enabled": True})
        elif it.get("type") == "builtin":
            bid = it.get("id", "")
            summary.append({"label": LABELS.get(bid, bid), "enabled": it.get("enabled", True)})
    await callback.answer("وضعیت دکمه تغییر کرد")
    try:
        await callback.message.edit_text(
            "📱 <b>ویرایش منوی اصلی</b>", parse_mode="HTML",
            reply_markup=await menu_editor_menu(summary),
        )
    except Exception:
        pass

@router.message(AdminState.tutitem_mediatitle)
async def process_tutitem_mediatitle(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    title = (message.text or "").strip()
    data = await state.get_data()
    tut_id = data.get("tutitem_tutorial_id")
    ctype = data.get("pending_ctype")
    fid = data.get("pending_fid")
    if not title:
        await message.answer("\u0639\u0646\u0648\u0627\u0646 \u0646\u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u062e\u0627\u0644\u06cc \u0628\u0627\u0634\u062f. \u06cc\u06a9 \u0639\u0646\u0648\u0627\u0646 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f:")
        return
    if not tut_id or not ctype or not fid:
        await state.clear()
        await message.answer("خطای وضعیت. دوباره تلاش کنید.", reply_markup=await back_to_admin())
        return
    await add_tutorial_item(tut_id, title[:60], ctype, "", fid)
    await state.clear()
    await message.answer(
        f"✅ زیرمجموعه «{title[:60]}» اضافه شد!",
        reply_markup=await tutorial_detail_menu(tut_id)
    )


@router.callback_query(F.data.startswith("adm_edit_tutitem_"))
async def cb_adm_edit_tutitem(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer()
        return
    item = await get_tutorial_item(item_id)
    if not item:
        await callback.answer("یافت نشد!", show_alert=True)
        return
    await state.update_data(edit_tutitem_id=item_id)
    await state.set_state(AdminState.tutitem_edit)
    ct_icons = {"TEXT": "📝", "PHOTO": "📷", "VIDEO": "🎬", "ANIMATION": "🎞"}
    icon = ct_icons.get(item["content_type"], "📄")
    await callback.message.edit_text(
        f"✏️ <b>ویرایش عنوان زیرمجموعه</b>\n\n"
        f"{icon} عنوان فعلی: <b>{item['title']}</b>\n\n"
        f"عنوان جدید را ارسال کنید:",
        parse_mode="HTML", reply_markup=await back_to_admin()
    )


@router.message(AdminState.tutitem_edit)
async def process_tutitem_edit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد. عنوان جدید را ارسال کنید:")
        return
    data = await state.get_data()
    item_id = data.get("edit_tutitem_id")
    item = await get_tutorial_item(item_id) if item_id else None
    if not item:
        await state.clear()
        await message.answer("آیتم یافت نشد.", reply_markup=await back_to_admin())
        return
    await update_tutorial_item(item_id, title=title[:60])
    await state.clear()
    await message.answer(
        f"✅ عنوان به «{title[:60]}» تغییر کرد.",
        reply_markup=await tutorial_detail_menu(item["tutorial_id"])
    )
