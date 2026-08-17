import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import is_admin
from api import panel_manager, panel_api
from keyboards.admin import back_to_admin

logger = logging.getLogger(__name__)
panel_router = Router()


class PanelState(StatesGroup):
    waiting_name = State()
    waiting_panel_type = State()
    waiting_url = State()
    waiting_username = State()
    waiting_password = State()
    waiting_inbound_select = State()
    waiting_sub_template = State()
    waiting_volume = State()
    waiting_edit_field = State()
    waiting_manual_link = State()
    waiting_panel_plan_name = State()
    waiting_panel_plan_gb = State()
    waiting_panel_plan_days = State()
    waiting_panel_plan_price = State()
    waiting_panel_plan_ip_limit = State()
    waiting_free_test_mb = State()
    waiting_free_test_days = State()
    waiting_wizard_ft_enabled = State()
    waiting_wizard_ft_mb = State()
    waiting_wizard_ft_days = State()
    waiting_wizard_ft_inbounds = State()
    waiting_panel_plan_edit = State()


def _is_admin_filter(user_id: int) -> bool:
    return user_id in (1,)  # placeholder, checked async


# ─── Panel List ────────────────────────────────────────────────
@panel_router.callback_query(F.data == "adm_panels")
async def cb_panels_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panels = await panel_manager._load_panels_from_db()
    if not panels:
        text = "📦 **مدیریت پنل‌ها**\n\nهیچ پنلی متصل نیست.\nبرای افزودن پنل جدید، دکمه زیر را بزنید."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن پنل", callback_data="adm_add_panel")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_menu")],
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return

    import database as db
    lines = ["📦 **مدیریت پنل‌ها**\n"]
    active_count = 0
    for p in panels:
        status = "🟢" if p.get("is_active") else "⚪"
        if p.get("is_active"):
            active_count += 1
        default = " ⭐" if p.get("is_default") else ""
        plans_count = await db.get_plans_count_by_panel(p["id"])
        configs_count = await db.get_configs_count_by_panel(p["id"])
        url_display = p['url'][:40] + "..." if len(p['url']) > 40 else p['url']
        sub_link = p.get("sub_link_template") or "خودکار (تشخیص خودکار)"
        lines.append(f"{status} **{p['name']}**{default}")
        lines.append(f"   URL: `{url_display}`")
        lines.append(f"   🔗 Sub: `{sub_link}`")
        lines.append(f"   پلن‌ها: {plans_count} | کانفیگ‌ها: {configs_count}")
        lines.append("")
    lines.append(f"تعداد پنل‌ها: {len(panels)} | فعال: {active_count}")

    kb_rows = []
    for p in panels:
        status_icon = "🟢" if p.get("is_active") else "⚪"
        default_icon = "⭐" if p.get("is_default") else ""
        btn_text = f"{status_icon}{default_icon} {p['name']}"
        btn_kwargs = {"text": btn_text, "callback_data": f"adm_panel_detail_{p['id']}"}
        if p.get("emoji_id"):
            btn_kwargs["icon_custom_emoji_id"] = p["emoji_id"]
        kb_rows.append([InlineKeyboardButton(**btn_kwargs)])
    kb_rows.append([InlineKeyboardButton(text="➕ افزودن پنل", callback_data="adm_add_panel")])
    kb_rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_menu")])

    await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")
    await callback.answer()


# ─── Panel Detail ──────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_detail_"))
async def cb_panel_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    status = "🟢 فعال" if panel.get("is_active") else "🔴 غیرفعال"
    default = " (پیش‌فرض ⭐)" if panel.get("is_default") else ""
    inbound_count = len([x for x in (panel.get("inbound_ids") or "").split(",") if x.strip()])
    plans_count = await db.get_plans_count_by_panel(panel_id)
    configs_count = await db.get_configs_count_by_panel(panel_id)
    volume_gb = panel.get("volume_gb", 0)
    volume_text = f"{volume_gb} GB" if volume_gb > 0 else "نامحدود"

    ptype = panel.get("panel_type", "v2ray")
    type_labels = {"wireguard": "🛡️ Azumi (Wireguard)", "pasarguard": "🛡️ PasarGuard", "3xui": "🔗 3x-ui (V2Ray/Xray)"}
    type_label = type_labels.get(ptype, "🔗 3x-ui (V2Ray/Xray)")

    text = (
        "📋 جزئیات پنل\n\n"
        "نام: " + panel['name'] + default + "\n"
        "نوع: " + type_label + "\n"
        "URL: " + panel['url'] + "\n"
        "وضعیت: " + status + "\n"
        "حجم فروش: " + volume_text + "\n"
    )
    if ptype == "3xui":
        text += (
            "نام کاربری: " + panel['username'] + "\n"
            "اینبوندها: " + str(inbound_count) + "\n"
            "قالب لینک: " + (panel.get('sub_link_template') or 'خودکار') + "\n"
        )
    elif ptype == "pasarguard":
        text += (
            "نام کاربری: " + panel['username'] + "\n"
            "مسیر اشتراک: sub\n"
        )
    text += "پلن‌ها: " + str(plans_count) + " | کانفیگ‌ها: " + str(configs_count)

    ft_enabled = panel.get("free_test_enabled", 0)
    ft_mb = panel.get("free_test_mb", 0)
    ft_days = panel.get("free_test_days", 1)
    ft_status = "🟢 فعال" if ft_enabled else "🔴 غیرفعال"
    ft_mb_text = f"{ft_mb // 1024} GB" if ft_mb >= 1024 else f"{ft_mb} MB"
    text += f"\n\n🧪 تست رایگان: {ft_status}"
    if ft_enabled:
        text += f"\n   حجم: {ft_mb_text} | مدت: {ft_days} روز"

    toggle_text = "🔴 غیرفعال کردن" if panel.get("is_active") else "🟢 فعال کردن"
    kb_rows = [
        [
            InlineKeyboardButton(text="🧪 تست اتصال", callback_data=f"adm_test_panel_{panel_id}"),
            InlineKeyboardButton(text="📋 پلن‌ها", callback_data=f"adm_panel_plans_{panel_id}"),
        ],
    ]
    if ptype == "3xui":
        kb_rows.append([
            InlineKeyboardButton(text="📥 اینبوندها", callback_data=f"adm_panel_inbounds_{panel_id}"),
            InlineKeyboardButton(text="👥 کلاینت‌ها", callback_data=f"adm_panel_clients_{panel_id}"),
        ])
    kb_rows.append([
        InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"adm_panel_edit_menu_{panel_id}"),
        InlineKeyboardButton(text=toggle_text, callback_data=f"adm_toggle_panel_{panel_id}"),
    ])
    kb_rows.append([
        InlineKeyboardButton(text="🧪 تست رایگان", callback_data=f"adm_panel_free_test_{panel_id}"),
    ])
    kb_rows.append([
        InlineKeyboardButton(text="⭐ پیش‌فرض", callback_data=f"adm_set_default_{panel_id}"),
        InlineKeyboardButton(text="🗑 حذف", callback_data=f"adm_delete_panel_{panel_id}"),
    ])
    kb_rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_panels")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Free Trial Settings ─────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_free_test_"))
async def cb_panel_free_test(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    ft_enabled = panel.get("free_test_enabled", 0)
    ft_mb = panel.get("free_test_mb", 102400)
    ft_days = panel.get("free_test_days", 1)
    ft_inbounds = panel.get("free_test_inbound_ids", "")

    status = "🟢 فعال" if ft_enabled else "🔴 غیرفعال"
    mb_text = f"{ft_mb // 1024} GB" if ft_mb >= 1024 else f"{ft_mb} MB"
    ib_count = len([x for x in ft_inbounds.split(",") if x.strip()]) if ft_inbounds else 0

    text = (
        f"🧪 **تنظیمات تست رایگان**\n\n"
        f"پنل: **{panel['name']}**\n"
        f"وضعیت: {status}\n"
        f"حجم: {mb_text}\n"
        f"مدت: {ft_days} روز\n"
        f"اینبوندها: {ib_count if ib_count > 0 else 'پیش‌فرض'}\n\n"
        "فیلد مورد نظر برای تغییر را انتخاب کنید:"
    )

    toggle_text = "🔴 غیرفعال کردن" if ft_enabled else "🟢 فعال کردن"
    kb_rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_toggle_free_test_{panel_id}")],
        [InlineKeyboardButton(text="📊 حجم (MB)", callback_data=f"adm_set_ft_mb_{panel_id}")],
        [InlineKeyboardButton(text="📅 مدت (روز)", callback_data=f"adm_set_ft_days_{panel_id}")],
        [InlineKeyboardButton(text="📥 اینبوندها", callback_data=f"adm_set_ft_inbounds_{panel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_toggle_free_test_"))
async def cb_toggle_free_test(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    new_val = 0 if panel.get("free_test_enabled", 0) else 1
    await db.update_panel(panel_id, free_test_enabled=new_val)
    status = "فعال" if new_val else "غیرفعال"
    await callback.answer(f"تست رایگان {status} شد!", show_alert=True)
    await cb_panel_free_test(callback)


@panel_router.callback_query(F.data.startswith("adm_set_ft_mb_"))
async def cb_set_ft_mb_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await state.update_data(ft_panel_id=panel_id)
    await state.set_state(PanelState.waiting_free_test_mb)
    text = (
        "📊 **حجم تست رایگان**\n\n"
        "حجم را به مگابایت وارد کنید:\n"
        "مثال: `1024` (1GB) یا `102400` (100GB)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_free_test_{panel_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_free_test_mb)
async def process_ft_mb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        mb = int(message.text.strip())
        if mb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return

    data = await state.get_data()
    panel_id = data["ft_panel_id"]
    import database as db
    await db.update_panel(panel_id, free_test_mb=mb)
    await state.clear()
    mb_text = f"{mb // 1024} GB" if mb >= 1024 else f"{mb} MB"
    await message.answer(
        f"✅ حجم تست رایگان به **{mb_text}** تغییر کرد.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧪 تنظیمات تست رایگان", callback_data=f"adm_panel_free_test_{panel_id}")]
        ]),
    )


@panel_router.callback_query(F.data.startswith("adm_set_ft_days_"))
async def cb_set_ft_days_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await state.update_data(ft_panel_id=panel_id)
    await state.set_state(PanelState.waiting_free_test_days)
    text = (
        "📅 **مدت تست رایگان**\n\n"
        "مدت را به روز وارد کنید:\n"
        "مثال: `1` یا `7`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_free_test_{panel_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_free_test_days)
async def process_ft_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return

    data = await state.get_data()
    panel_id = data["ft_panel_id"]
    import database as db
    await db.update_panel(panel_id, free_test_days=days)
    await state.clear()
    await message.answer(
        f"✅ مدت تست رایگان به **{days} روز** تغییر کرد.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧪 تنظیمات تست رایگان", callback_data=f"adm_panel_free_test_{panel_id}")]
        ]),
    )


@panel_router.callback_query(F.data.startswith("adm_set_ft_inbounds_"))
async def cb_set_ft_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    inbounds = await panel_manager.get_inbounds_summary(panel_id)
    if not inbounds:
        await callback.answer("اینبوندی یافت نشد!", show_alert=True)
        return

    current_str = panel.get("free_test_inbound_ids", "")
    current_ids = {int(x.strip()) for x in current_str.split(",") if x.strip().isdigit()} if current_str else set()

    lines = ["📥 **اینبوندهای تست رایگان**\n"]
    kb_rows = []
    for ib in inbounds:
        is_selected = ib["id"] in current_ids
        check = "☑" if is_selected else "☐"
        lines.append(f"{check} {ib['tag']} ({ib['protocol']})")
        kb_rows.append([InlineKeyboardButton(
            text=f"{check} {ib['tag']} ({ib['protocol']})",
            callback_data=f"adm_toggle_ft_ib_{panel_id}_{ib['id']}"
        )])
    kb_rows.append([InlineKeyboardButton(text="✅ تایید", callback_data=f"adm_panel_free_test_{panel_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_toggle_ft_ib_"))
async def cb_toggle_ft_inbound(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    ib_id = int(parts[-1])

    import database as db
    panel = await db.get_panel(panel_id)
    current_str = panel.get("free_test_inbound_ids", "")
    current_ids = {int(x.strip()) for x in current_str.split(",") if x.strip().isdigit()} if current_str else set()

    if ib_id in current_ids:
        current_ids.discard(ib_id)
    else:
        current_ids.add(ib_id)

    new_ids_str = ",".join(str(x) for x in sorted(current_ids))
    await db.update_panel(panel_id, free_test_inbound_ids=new_ids_str)
    await cb_set_ft_inbounds(callback)


# ─── Add Panel Wizard ─────────────────────────────────────────
@panel_router.callback_query(F.data == "adm_add_panel")
async def cb_add_panel_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(PanelState.waiting_name)
    await state.update_data(wizard_inbounds={})
    text = (
        f"➕ **افزودن پنل** (مرحله ۱ از ۶)\n\n"
        "نام پنل را وارد کنید (مثال: `Panel 1`):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_name)
async def process_panel_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("نام خیلی کوتاه است. حداقل ۲ کاراکتر وارد کنید.")
        return
    await state.update_data(panel_name=name)
    await state.set_state(PanelState.waiting_panel_type)
    text = (
        f"➕ **افزودن پنل: {name}** (مرحله ۲ از ۵)\n\n"
        "نوع پنل را انتخاب کنید:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 3x-ui (V2Ray/Xray)", callback_data="adm_panel_type_3xui")],
        [InlineKeyboardButton(text="🛡️ Azumi (Wireguard)", callback_data="adm_panel_type_wireguard")],
        [InlineKeyboardButton(text="🛡️ PasarGuard", callback_data="adm_panel_type_pasarguard")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@panel_router.callback_query(F.data.startswith("adm_panel_type_"))
async def cb_select_panel_type(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    panel_type = callback.data.split("_")[-1]
    await state.update_data(panel_type=panel_type)
    data = await state.get_data()
    name = data.get("panel_name", "")
    if panel_type == "wireguard":
        await state.set_state(PanelState.waiting_url)
        text = (
            f"➕ **افزودن پنل: {name}** (مرحله ۳ از ۵)\n\n"
            "🛡️ **پنل Azumi Wireguard**\n\n"
            "آدرس پنل Wireguard را وارد کنید:\n"
            "(مثال: `http://panel.example.com:8085`)\n\n"
            "_پنل Wireguard نیازی به نام کاربری و رمز عبور ندارد._"
        )
    elif panel_type == "pasarguard":
        await state.set_state(PanelState.waiting_url)
        text = (
            f"➕ **افزودن پنل: {name}** (مرحله ۳ از ۵)\n\n"
            "🛡️ **پنل PasarGuard**\n\n"
            "آدرس پنل PasarGuard را وارد کنید:\n"
            "(مثال: `https://panel.example.com`)\n\n"
            "_پس از وارد کردن آدرس، نام کاربری و رمز عبور پرسیده می‌شود._"
        )
    else:
        await state.set_state(PanelState.waiting_url)
        text = (
            f"➕ **افزودن پنل: {name}** (مرحله ۳ از ۶)\n\n"
            "آدرس پنل 3x-ui را وارد کنید:\n"
            "(مثال: `https://panel.example.com`)"
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_url)
async def process_panel_url(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    url = message.text.strip().rstrip("/")
    if not url.startswith("http"):
        await message.answer("آدرس باید با `http://` یا `https://` شروع شود.", parse_mode="Markdown")
        return
    await state.update_data(panel_url=url)
    data = await state.get_data()
    panel_type = data.get("panel_type", "3xui")
    if panel_type == "wireguard":
        loading_msg = await message.answer("⏳ در حال تصت اتصال به پنل Wireguard...")
        from wireguard_api import WireguardAPI
        temp_wg = WireguardAPI(panel_url=url)
        try:
            ok = await temp_wg.health_check()
        except Exception:
            ok = False
        finally:
            await temp_wg.close()
        if not ok:
            text = "❌ خطا در اتصال به پنل Wireguard\n\nآیا می‌خواهید دوباره تلاش کنید?"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 تلاش مجدد", callback_data="adm_retry_panel_url")],
                [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
            ])
            await loading_msg.edit_text(text, reply_markup=kb)
            return
        await state.update_data(panel_username="wg_admin", panel_password="", panel_inbound_ids="", panel_sub_template="")
        await state.set_state(PanelState.waiting_volume)
        await loading_msg.edit_text(
            "✅ اتصال به پنل Wireguard موفق!\n\n"
            "حجم کل فروش پنل را به گیگابایت وارد کنید:\n"
            "(۰ = بدون محدودیت)"
        )
        return
    if panel_type == "pasarguard":
        await state.set_state(PanelState.waiting_username)
        text = (
            f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۴ از ۵)\n\n"
            "نام کاربری پنل PasarGuard را وارد کنید:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
        ])
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        return
    await state.set_state(PanelState.waiting_username)
    text = (
        f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۳ از ۶)\n\n"
        "نام کاربری پنل را وارد کنید:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")
@panel_router.message(PanelState.waiting_username)
async def process_panel_username(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    username = message.text.strip()
    if not username:
        await message.answer("نام کاربری نمی‌تواند خالی باشد.")
        return
    await state.update_data(panel_username=username)
    await state.set_state(PanelState.waiting_password)
    data = await state.get_data()
    text = (
        f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۴ از ۶)\n\n"
        "رمز عبور پنل را وارد کنید:\n"
        "_(پس از ارسال، اتصال به صورت خودکار تست می‌شود)_"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@panel_router.message(PanelState.waiting_password)
async def process_panel_password(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    password = message.text.strip()
    if not password:
        await message.answer("رمز عبور نمی‌تواند خالی باشد.")
        return
    await state.update_data(panel_password=password)
    data = await state.get_data()

    loading_msg = await message.answer("⏳ در حال تست اتصال...")

    if data.get("panel_type") == "pasarguard":
        from pasarguard_api import PasarGuardAPI
        temp_pg = PasarGuardAPI(
            panel_url=data["panel_url"],
            panel_user=data["panel_username"],
            panel_pass=password,
        )
        try:
            ok = await temp_pg.login()
        except Exception:
            ok = False
        finally:
            await temp_pg.close()

        if not ok:
            text = "❌ خطا در اتصال به پنل PasarGuard\n\nآیا می‌خواهید دوباره تلاش کنید?"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 تلاش مجدد", callback_data="adm_retry_panel_password")],
                [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
            ])
            await loading_msg.edit_text(text, reply_markup=kb)
            return

        await state.update_data(panel_inbound_ids="", panel_sub_template="")
        await state.set_state(PanelState.waiting_volume)
        await loading_msg.edit_text(
            "✅ اتصال به پنل PasarGuard موفق!\n\n"
            "حجم کل فروش پنل را به گیگابایت وارد کنید:\n"
            "(۰ = بدون محدودیت)"
        )
        return

    result = await panel_manager.test_connection_with_creds(
        url=data["panel_url"],
        username=data["panel_username"],
        password=password,
    )

    if not result["success"]:
        text = (
            "❌ خطا در اتصال\n\n"
            "خطا: " + str(result['error']) + "\n\n"
            "آیا می‌خواهید دوباره تلاش کنید؟"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تلاش مجدد", callback_data="adm_retry_panel_password")],
            [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
        ])
        await loading_msg.edit_text(text, reply_markup=kb)
        return

    inbounds = result.get("inbounds", [])
    # Auto-select all inbounds and save
    all_inbound_ids = [str(ib["id"]) for ib in inbounds]
    inbound_ids_str = ",".join(all_inbound_ids)
    await state.update_data(panel_inbound_ids=inbound_ids_str)
    await state.set_state(PanelState.waiting_sub_template)

    text = (
        "✅ اتصال موفق!\n\n"
        "اینبوندها: " + str(result['inbounds_count']) + " | کلاینت‌ها: " + str(result['total_clients']) + "\n\n"
        "قالب لینک اشتراک را وارد کنید:\n"
        "مثال: https://domain.com/sub/XYZ\n\n"
        "یا برای تشخیص خودکار، دکمه رد شدن را بزنید."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ رد شدن (خودکار)", callback_data="adm_skip_sub_template")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
    ])
    await loading_msg.edit_text(text, reply_markup=kb)


@panel_router.callback_query(F.data == "adm_retry_panel_url")
async def cb_retry_panel_url(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(PanelState.waiting_url)
    data = await state.get_data()
    text = (
        f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۳ از ۵)\n\n"
        "آدرس پنل Wireguard را دوباره وارد کنید:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data == "adm_retry_panel_password")
async def cb_retry_panel_password(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(PanelState.waiting_password)
    data = await state.get_data()
    text = (
        f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۴ از ۶)\n\n"
        "رمز عبور پنل را دوباره وارد کنید:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_wiz_panel_ib_"))
async def cb_toggle_inbound(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    ib_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    selected = data.get("wizard_inbounds", {})
    if ib_id in selected:
        del selected[ib_id]
    else:
        selected[ib_id] = True
    await state.update_data(wizard_inbounds=selected)

    all_inbounds = data.get("wizard_all_inbounds", [])
    lines = [
        "✅ **اینبوندهای مورد نظر را انتخاب کنید:**\n",
    ]
    kb_rows = []
    for ib in all_inbounds:
        is_selected = ib["id"] in selected
        icon = "✅" if ib.get("enable") else "⏸"
        check = "☑" if is_selected else "☐"
        text_line = f"{check} {ib['tag']} ({ib['protocol']}) - {ib['client_count']} کلاینت"
        lines.append(text_line)
        cb_data = f"adm_wiz_panel_ib_{ib['id']}"
        kb_rows.append([InlineKeyboardButton(text=f"{check} {ib['tag']} ({ib['protocol']})", callback_data=cb_data)])

    if selected:
        kb_rows.append([InlineKeyboardButton(text=f"✅ تایید ({len(selected)} انتخاب شده)", callback_data="adm_confirm_panel_inbounds")])
    else:
        kb_rows.append([InlineKeyboardButton(text="⚠️ حداقل ۱ اینبوند انتخاب کنید", callback_data="noop")])
    kb_rows.append([InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")])

    await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data == "adm_confirm_panel_inbounds")
async def cb_confirm_inbounds(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    selected = data.get("wizard_inbounds", {})
    if not selected:
        await callback.answer("حداقل ۱ اینبوند انتخاب کنید!", show_alert=True)
        return

    inbound_ids_str = ",".join(str(x) for x in selected.keys())
    await state.update_data(panel_inbound_ids=inbound_ids_str)
    await state.set_state(PanelState.waiting_sub_template)

    text = (
        f"➕ **افزودن پنل: {data['panel_name']}** (مرحله ۵ از ۶)\n\n"
        "قالب لینک اشتراک را وارد کنید:\n"
        "مثال: https://domain.com/sub/{{sub_id}}\n\n"
        "یا برای تشخیص خودکار، دکمه رد شدن را بزنید."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ رد شدن (خودکار)", callback_data="adm_skip_sub_template")],
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm_panels")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_sub_template)
async def process_sub_template(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    template = message.text.strip()
    await state.update_data(panel_sub_template=template)
    await state.set_state(PanelState.waiting_volume)
    await message.answer(
        "حجم کل فروش پنل را به گیگابایت وارد کنید:\n"
        "(۰ = بدون محدودیت)"
    )


@panel_router.callback_query(F.data == "adm_skip_sub_template")
async def cb_skip_sub_template(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.update_data(panel_sub_template="")
    await state.set_state(PanelState.waiting_volume)
    await callback.message.edit_text(
        "حجم کل فروش پنل را به گیگابایت وارد کنید:\n"
        "(۰ = بدون محدودیت)"
    )
    await callback.answer()


@panel_router.message(PanelState.waiting_volume)
async def process_volume(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        volume = int(message.text.strip())
        if volume < 0:
            raise ValueError
    except ValueError:
        await message.answer("عدد نامعتبر. یک عدد غیرمنفی وارد کنید:")
        return
    await state.update_data(panel_volume_gb=volume)
    panel_type = (await state.get_data()).get("panel_type", "3xui")
    if panel_type in ("wireguard", "pasarguard"):
        await _finalize_panel_add(message, state)
        return
    await state.set_state(PanelState.waiting_wizard_ft_enabled)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ فعال", callback_data="adm_wiz_ft_enable_1")],
        [InlineKeyboardButton(text="❌ غیرفعال", callback_data="adm_wiz_ft_enable_0")],
    ])
    await message.answer(
        "آیا تست رایگان برای این پنل فعال باشد?",
        reply_markup=kb
    )


@panel_router.callback_query(F.data.startswith("adm_wiz_ft_enable_"))
async def cb_wiz_ft_enable(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    enabled = int(callback.data.split("_")[-1])
    await state.update_data(wizard_ft_enabled=enabled)
    if not enabled:
        await _finalize_panel_add(callback.message, state)
        return
    await state.set_state(PanelState.waiting_wizard_ft_mb)
    await callback.message.edit_text(
        "📊 حجم تست رایگان را به مگابایت وارد کنید:\n"
        "(مثال: 100 = 100 مگابایت)"
    )
    await callback.answer()


@panel_router.message(PanelState.waiting_wizard_ft_mb)
async def process_wiz_ft_mb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        mb = int(message.text.strip())
        if mb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(wizard_ft_mb=mb)
    await state.set_state(PanelState.waiting_wizard_ft_days)
    await message.answer(
        "📅 مدت تست رایگان را به روز وارد کنید:\n"
        "(مثال: 1)"
    )


@panel_router.message(PanelState.waiting_wizard_ft_days)
async def process_wiz_ft_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(wizard_ft_days=days)
    await _show_wizard_ft_inbounds(message, state)


async def _show_wizard_ft_inbounds(message, state):
    data = await state.get_data()
    panel_url = data.get("panel_url", "")
    panel_username = data.get("panel_username", "")
    panel_password = data.get("panel_password", "")
    inbounds = []
    try:
        temp_api = PanelAPI(panel_url=panel_url, panel_user=panel_username, panel_pass=panel_password)
        inbounds = await temp_api.get_inbounds()
        await temp_api.close()
    except Exception:
        pass
    if not inbounds:
        await state.update_data(wizard_ft_inbound_ids="")
        await _finalize_panel_add(message, state)
        return
    await state.update_data(wizard_all_ft_inbounds=inbounds, wizard_ft_selected_inbounds={})
    lines = ["📥 **اینبوندهای تست رایگان را انتخاب کنید:**\n"]
    kb_rows = []
    for ib in inbounds:
        cb_data = f"adm_wiz_ft_ib_{ib['id']}"
        kb_rows.append([InlineKeyboardButton(
            text=f"☐ {ib.get('tag', '?')} ({ib.get('protocol', '?')})",
            callback_data=cb_data
        )])
    kb_rows.append([InlineKeyboardButton(text="✅ تایید", callback_data="adm_wiz_ft_ib_done")])
    kb_rows.append([InlineKeyboardButton(text="⏭️ رد شدن", callback_data="adm_wiz_ft_skip_all")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await state.set_state(PanelState.waiting_wizard_ft_inbounds)
    await message.answer("\n".join(lines), reply_markup=kb, parse_mode="Markdown")


@panel_router.callback_query(F.data.startswith("adm_wiz_ft_ib_"))
async def cb_wiz_ft_toggle_inbound(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    try:
        ib_id = int(parts[-1])
    except ValueError:
        return
    data = await state.get_data()
    selected = data.get("wizard_ft_selected_inbounds", {})
    if ib_id in selected:
        del selected[ib_id]
    else:
        selected[ib_id] = True
    await state.update_data(wizard_ft_selected_inbounds=selected)

    all_inbounds = data.get("wizard_all_ft_inbounds", [])
    kb_rows = []
    for ib in all_inbounds:
        is_sel = ib["id"] in selected
        check = "☑" if is_sel else "☐"
        kb_rows.append([InlineKeyboardButton(
            text=f"{check} {ib.get('tag', '?')} ({ib.get('protocol', '?')})",
            callback_data=f"adm_wiz_ft_ib_{ib['id']}"
        )])
    if selected:
        kb_rows.append([InlineKeyboardButton(text=f"✅ تایید ({len(selected)} انتخاب شده)", callback_data="adm_wiz_ft_ib_done")])
    else:
        kb_rows.append([InlineKeyboardButton(text="⚠️ حداقل ۱ اینبوند انتخاب کنید", callback_data="noop")])
    kb_rows.append([InlineKeyboardButton(text="⏭️ رد شدن", callback_data="adm_wiz_ft_skip_all")])
    await callback.message.edit_reply_markup(InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await callback.answer()


@panel_router.callback_query(F.data == "adm_wiz_ft_ib_done")
async def cb_wiz_ft_ib_confirm(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    selected = data.get("wizard_ft_selected_inbounds", {})
    inbound_ids_str = ",".join(str(x) for x in selected.keys())
    await state.update_data(wizard_ft_inbound_ids=inbound_ids_str)
    await _finalize_panel_add(callback.message, state)


@panel_router.callback_query(F.data == "adm_wiz_ft_skip_all")
async def cb_wiz_ft_ib_skip(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.update_data(wizard_ft_inbound_ids="")
    await _finalize_panel_add(callback.message, state)


async def _finalize_panel_add(message: Message, state: FSMContext):
    data = await state.get_data()
    panel_type = data.get("panel_type", "3xui")
    try:
        instance = await panel_manager.add({
            "name": data["panel_name"],
            "url": data["panel_url"],
            "username": data.get("panel_username", ""),
            "password": data.get("panel_password", ""),
            "sub_link_template": data.get("panel_sub_template", ""),
            "inbound_ids": data.get("panel_inbound_ids", ""),
            "is_default": False,
            "volume_gb": data.get("panel_volume_gb", 0),
            "panel_type": panel_type,
            "free_test_enabled": data.get("wizard_ft_enabled", 0),
            "free_test_mb": data.get("wizard_ft_mb", 102400),
            "free_test_days": data.get("wizard_ft_days", 1),
            "free_test_inbound_ids": data.get("wizard_ft_inbound_ids", ""),
        })
        # Auto-create plan section for this panel
        import database as db
        section_id = await db.add_plan_section(
            name=data["panel_name"],
            display_order=0,
            panel_id=instance.panel_id,
        )
        await state.clear()
        volume_text = f"{data.get('panel_volume_gb', 0)} GB" if data.get('panel_volume_gb', 0) > 0 else "نامحدود"
        text = (
            "✅ پنل " + data['panel_name'] + " اضافه شد!\n\n"
            "حجم فروش: " + volume_text + "\n"
            "دسته پلن‌ها: " + data['panel_name'] + " (خودکار ایجاد شد)\n\n"
            "آیا این پنل را به عنوان پیش‌فرض تنظیم کنم؟"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ بله، پیش‌فرض", callback_data=f"adm_set_def_new_yes_{instance.panel_id}")],
            [InlineKeyboardButton(text="❌ خیر", callback_data="adm_set_default_new_no")],
        ])
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to add panel: {e}")
        await state.clear()
        await message.answer(f"❌ خطا در افزودن پنل: {e}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm_panels")]
        ]))


@panel_router.callback_query(F.data.startswith("adm_set_def_new_yes_"))
async def cb_set_default_new_yes(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await panel_manager.set_default(panel_id)
    await callback.message.edit_text(
        "⭐ **پنل به عنوان پیش‌فرض تنظیم شد!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 مدیریت پنل‌ها", callback_data="adm_panels")]
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


@panel_router.callback_query(F.data == "adm_set_default_new_no")
async def cb_set_default_new_no(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "✅ **پنل با موفقیت اضافه شد!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 مدیریت پنل‌ها", callback_data="adm_panels")]
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Test Connection ───────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_test_panel_"))
async def cb_test_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    loading = await callback.message.edit_text("⏳ در حال تست اتصال...")

    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    ptype = panel.get("panel_type", "v2ray")

    if ptype == "wireguard":
        from wireguard_api import WireguardAPI
        temp_api = WireguardAPI(panel_url=panel["url"])
        try:
            ok = await temp_api.health_check()
        except Exception:
            ok = False
        finally:
            await temp_api.close()

        if ok:
            text = (
                f"✅ **گزارش اتصال پنل Wireguard**\n\n"
                f"🔗 وضعیت: 🟢 فعال\n"
                f"📡 اینترفیس: wg0\n"
                f"🛡️ پنل Azumi: در دسترس"
            )
        else:
            text = (
                f"❌ **گزارش اتصال پنل Wireguard**\n\n"
                f"🔗 وضعیت: 🔴 غیرفعال\n"
                f"❌ خطا: اتصال به پنل برقرار نشد"
            )
    elif ptype == "pasarguard":
        from pasarguard_api import PasarGuardAPI
        temp_api = PasarGuardAPI(
            panel_url=panel["url"],
            panel_user=panel["username"],
            panel_pass=panel["password"],
        )
        try:
            login_ok = await temp_api.login()
            groups = await temp_api.get_groups() if login_ok else []
            users_data = await temp_api._get("/api/users") if login_ok else None
            user_count = len(users_data.get("users", [])) if isinstance(users_data, dict) else 0
        except Exception as e:
            login_ok = False
            groups = []
            user_count = 0
            logger.error(f"PasarGuard test error: {e}")
        finally:
            await temp_api.close()

        if login_ok:
            text = (
                f"✅ **گزارش اتصال پنل PasarGuard**\n\n"
                f"🔗 وضعیت: 🟢 فعال\n"
                f"🔐 ورود: 🟢 موفق\n"
                f"👥 کاربران: {user_count}\n"
                f"📂 گروه‌ها: {len(groups)}"
            )
        else:
            text = (
                f"❌ **گزارش اتصال پنل PasarGuard**\n\n"
                f"🔗 وضعیت: 🔴 غیرفعال\n"
                f"🔐 ورود: 🔴 ناموفق\n"
                f"❌ خطا: اتصال به پنل برقرار نشد"
            )
    else:
        result = await panel_manager.test_connection_detailed(panel_id)
        if result["success"]:
            proto_lines = []
            for proto, count in result.get("inbounds_by_protocol", {}).items():
                proto_lines.append(f"  • {proto}: {count}")
            proto_text = "\n".join(proto_lines) if proto_lines else "  —"

            text = (
                f"✅ **گزارش اتصال پنل**\n\n"
                f"🔗 وضعیت URL: {'🟢 قابل دسترس' if result['url_reachable'] else '🔴 غیرقابل دسترس'}\n"
                f"⚡ زمان پاسخ: {result['response_time_ms']}ms\n"
                f"🔐 ورود: {'🟢 موفق' if result['login_ok'] else '🔴 ناموفق'}\n"
                f"📡 اینبوندها: {result['inbounds_count']}\n"
                f"👥 کلاینت‌ها: {result['total_clients']}\n"
                f"📋 پروتکل‌ها:\n{proto_text}\n"
                f"🔗 قالب لینک: `{result['sub_template']}`"
            )
            if result.get("error"):
                text += f"\n\n⚠️ هشدار: {result['error']}"
        else:
            text = (
                f"❌ **گزارش اتصال پنل**\n\n"
                f"🔗 وضعیت URL: {'🟢 قابل دسترس' if result['url_reachable'] else '🔴 غیرقابل دسترس'}\n"
                f"🔐 ورود: {'🟢 موفق' if result['login_ok'] else '🔴 ناموفق'}\n"
                f"❌ خطا: {result['error']}"
            )

    kb_rows = [
        [InlineKeyboardButton(text="🔄 تست مجدد", callback_data=f"adm_test_panel_{panel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")],
    ]
    if ptype == "3xui":
        kb_rows.insert(0, [InlineKeyboardButton(text="📥 مشاهده اینبوندها", callback_data=f"adm_panel_inbounds_{panel_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Inbounds List ─────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_inbounds_"))
async def cb_panel_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    loading = await callback.message.edit_text("⏳ در حال دریافت اینبوندها...")

    inbounds = await panel_manager.get_inbounds_summary(panel_id)
    if not inbounds:
        await callback.message.edit_text(
            "❌ اینبوندی یافت نشد یا پنل در دسترس نیست.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")]
            ]),
        )
        await callback.answer()
        return

    lines = ["📥 **لیست اینبوندها**\n"]
    for ib in inbounds:
        icon = "🟢" if ib.get("enable") else "🔴"
        lines.append(f"{icon} **{ib['tag']}** ({ib['protocol']})")
        lines.append(f"   ID: `{ib['id']}` | کلاینت‌ها: {ib['client_count']}")
        lines.append("")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 مشاهده کلاینت‌ها", callback_data=f"adm_panel_clients_{panel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")],
    ])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Clients List ──────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_clients_"))
async def cb_panel_clients(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    loading = await callback.message.edit_text("⏳ در حال دریافت کلاینت‌ها...")

    clients = await panel_manager.get_all_clients(panel_id)
    if not clients:
        await callback.message.edit_text(
            "👥 **لیست کلاینت‌ها**\n\nهیچ کلاینتی یافت نشد.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")]
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    lines = [f"👥 **لیست کلاینت‌ها** ({len(clients)} نفر)\n"]
    for c in clients[:20]:
        icon = "🟢" if c.get("enable") else "🔴"
        total = c.get("total_gb", 0)
        gb_str = f"{total / (1024*1024*1024):.1f}GB" if total > 0 else "نامحدود"
        lines.append(f"{icon} `{c['email']}` | {gb_str} | Inbound: {c['inbound_tag']}")
    if len(clients) > 20:
        lines.append(f"\n... و {len(clients) - 20} کلاینت دیگر")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 اینبوندها", callback_data=f"adm_panel_inbounds_{panel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")],
    ])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Set Default ───────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_set_default_"))
async def cb_set_default(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await panel_manager.set_default(panel_id)
    await callback.answer("⭐ پنل پیش‌فرض تنظیم شد!", show_alert=True)
    await cb_panel_detail(callback)


# ─── Delete Panel ──────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_delete_panel_"))
async def cb_delete_panel_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    text = f"⚠️ **آیا از حذف پنل «{panel['name']}» مطمئنید؟**\n\nاین عمل قابل بازگشت نیست."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 بله، حذف شود", callback_data=f"adm_del_panel_yes_{panel_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"adm_panel_detail_{panel_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_del_panel_yes_"))
async def cb_delete_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await panel_manager.remove(panel_id)
    await callback.message.edit_text(
        "✅ **پنل با موفقیت حذف شد!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 مدیریت پنل‌ها", callback_data="adm_panels")]
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Edit Panel ────────────────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_edit_menu_"))
async def cb_edit_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    # Only handle adm_panel_edit_menu_{panel_id} (not fld_ or ib_ variants)
    data = callback.data
    if "_fld_" in data or "_ib_" in data:
        return  # Not our handler
    parts = data.split("_")
    panel_id = int(parts[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    ptype = panel.get("panel_type", "v2ray")
    text = (
        f"✏️ **ویرایش پنل: {panel['name']}**\n\n"
        f"URL: `{panel['url']}`\n"
    )
    if ptype == "3xui":
        text += (
            f"نام کاربری: `{panel['username']}`\n"
            f"قالب لینک: {'✅' if panel.get('sub_link_template') else '❌ خودکار'}\n"
        )
    elif ptype == "pasarguard":
        text += f"نام کاربری: `{panel['username']}`\n"
    text += "\nفیلد مورد نظر برای ویرایش را انتخاب کنید:"
    kb_rows = [
        [InlineKeyboardButton(text="🔗 آدرس پنل", callback_data=f"adm_panel_edit_menu_fld_url_{panel_id}")],
    ]
    if ptype == "3xui":
        kb_rows.extend([
            [InlineKeyboardButton(text="👤 نام کاربری", callback_data=f"adm_panel_edit_menu_fld_username_{panel_id}")],
            [InlineKeyboardButton(text="🔒 رمز عبور", callback_data=f"adm_panel_edit_menu_fld_password_{panel_id}")],
            [InlineKeyboardButton(text="📝 قالب لینک", callback_data=f"adm_panel_edit_menu_fld_template_{panel_id}")],
            [InlineKeyboardButton(text="🧪 تست قالب", callback_data=f"adm_test_sub_template_{panel_id}")],
            [InlineKeyboardButton(text="📥 اینبوندها", callback_data=f"adm_panel_edit_menu_ib_{panel_id}")],
        ])
    elif ptype == "pasarguard":
        kb_rows.extend([
            [InlineKeyboardButton(text="👤 نام کاربری", callback_data=f"adm_panel_edit_menu_fld_username_{panel_id}")],
            [InlineKeyboardButton(text="🔒 رمز عبور", callback_data=f"adm_panel_edit_menu_fld_password_{panel_id}")],
        ])
    kb_rows.append([InlineKeyboardButton(text="🎯 ایموجی پنل", callback_data=f"adm_panel_emoji_{panel_id}")])
    kb_rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_edit_menu_fld_"))
async def cb_edit_panel_field(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    field = parts[-2]
    panel_id = int(parts[-1])
    await state.update_data(edit_panel_id=panel_id, edit_panel_field=field)
    await state.set_state(PanelState.waiting_edit_field)

    field_names = {
        "url": "آدرس پنل",
        "username": "نام کاربری",
        "password": "رمز عبور",
        "template": "قالب لینک اشتراک",
    }
    prompts = {
        "url": "آدرس جدید پنل را وارد کنید (مثال: `https://panel.example.com`):",
        "username": "نام کاربری جدید را وارد کنید:",
        "password": "رمز عبور جدید را وارد کنید:",
        "template": "قالب لینک جدید را وارد کنید (مثال: `https://domain.com/sub/{sub_id}`):\n\nیا برای تشخیص خودکار `خودکار` تایپ کنید:",
    }

    text = f"✏️ **ویرایش {field_names.get(field, field)}**\n\n{prompts.get(field, 'مقدار جدید را وارد کنید:')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_edit_menu_{panel_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_emoji_"))
async def cb_emoji_id(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-1])
    await state.update_data(edit_panel_id=panel_id, edit_panel_field="emoji")
    await state.set_state(PanelState.waiting_edit_field)
    import database as db
    panel = await db.get_panel(panel_id)
    current = panel.get("emoji_id", "") or "خالی"
    text = (
        f"🎯 **ایموجی پنل: {panel['name']}**\n\n"
        f"مقدار فعلی: `{current}`\n\n"
        f"Premium Emoji ID را وارد کنید:\n"
        f"(برای حذف ایموجی `خالی` تایپ کنید)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_edit_menu_{panel_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_edit_field)
async def process_edit_field(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    panel_id = data["edit_panel_id"]
    field = data["edit_panel_field"]
    value = message.text.strip()

    updates = {}
    if field == "url":
        if not value.startswith("http") or "." not in value:
            await message.answer("آدرس معتبر نیست. دوباره تلاش کنید.")
            return
        updates["url"] = value.rstrip("/")
    elif field == "username":
        updates["username"] = value
    elif field == "password":
        updates["password"] = value
    elif field == "template":
        updates["sub_link_template"] = "" if value == "خودکار" else value
    elif field == "emoji":
        updates["emoji_id"] = "" if value == "خالی" else value

    await panel_manager.update(panel_id, **updates)
    await state.clear()
    await message.answer(
        "✅ **فیلد با موفقیت به‌روزرسانی شد!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")]
        ]),
        parse_mode="Markdown",
    )


# ─── Sub Template Testing ─────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_test_sub_template_"))
async def cb_test_sub_template(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    current_template = panel.get("sub_link_template", "")
    sample_sub_id = "abc123def456ghi7"

    if current_template:
        sample_link = current_template.replace("{sub_id}", sample_sub_id).replace("{id}", sample_sub_id)
        text = (
            f"🔗 **قالب لینک اشتراک**\n\n"
            f"الان: `{current_template}`\n\n"
            f"نمونه خروجی:\n`{sample_link}`"
        )
    else:
        text = (
            f"🔗 **قالب لینک اشتراک**\n\n"
            f"الان: **خودکار** (تشخیص از آدرس پنل)\n\n"
            f"نمونه خروجی:\n`https://domain.com:2096/sub/{sample_sub_id}`\n\n"
            f"_(برای سفارشی کردن، قالب جدید وارد کنید)_"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ تغییر قالب", callback_data=f"adm_panel_edit_menu_fld_template_{panel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_edit_menu_{panel_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_edit_menu_ib_"))
async def cb_edit_panel_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    loading = await callback.message.edit_text("⏳ در حال دریافت اینبوندها...")

    inbounds = await panel_manager.get_inbounds_summary(panel_id)
    if not inbounds:
        await callback.message.edit_text(
            "❌ اینبوندی یافت نشد.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")]
            ]),
        )
        await callback.answer()
        return

    import database as db
    panel = await db.get_panel(panel_id)
    current_ids = set()
    if panel and panel.get("inbound_ids"):
        current_ids = {int(x.strip()) for x in panel["inbound_ids"].split(",") if x.strip().isdigit()}

    lines = ["📥 **انتخاب اینبوندها**\n"]
    kb_rows = []
    for ib in inbounds:
        is_selected = ib["id"] in current_ids
        check = "☑" if is_selected else "☐"
        lines.append(f"{check} {ib['tag']} ({ib['protocol']}) - {ib['client_count']} کلاینت")
        kb_rows.append([InlineKeyboardButton(text=f"{check} {ib['tag']} ({ib['protocol']})", callback_data=f"adm_toggle_edit_ib_{panel_id}_{ib['id']}")])

    kb_rows.append([InlineKeyboardButton(text="✅ تایید", callback_data=f"adm_confirm_edit_inbounds_{panel_id}")])
    kb_rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")])

    await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_toggle_edit_ib_"))
async def cb_toggle_edit_inbound(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    ib_id = int(parts[-1])

    import database as db
    panel = await db.get_panel(panel_id)
    current_ids = set()
    if panel and panel.get("inbound_ids"):
        current_ids = {int(x.strip()) for x in panel["inbound_ids"].split(",") if x.strip().isdigit()}

    if ib_id in current_ids:
        current_ids.discard(ib_id)
    else:
        current_ids.add(ib_id)

    new_ids_str = ",".join(str(x) for x in sorted(current_ids))
    await db.update_panel(panel_id, inbound_ids=new_ids_str)
    await panel_manager.update(panel_id, inbound_ids=new_ids_str)

    await cb_edit_panel_inbounds(callback)


@panel_router.callback_query(F.data.startswith("adm_confirm_edit_inbounds_"))
async def cb_confirm_edit_inbounds(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        "✅ **اینبوندها با موفقیت به‌روزرسانی شدند!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")]
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Panel Plans Management ───────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_panel_plans_"))
async def cb_panel_plans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    plans = await db.get_plans_by_panel(panel_id)
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return

    lines = [f"📋 **پلن‌های پنل: {panel['name']}**\n"]
    if not plans:
        lines.append("هیچ پلنی برای این پنل تعریف نشده است.")
    else:
        for p in plans:
            status = "🟢" if p.get("is_active") else "🔴"
            lines.append(f"{status} **{p['name']}** — {p['gb']}GB / {p['days']} روز")
            lines.append(f"   💰 {p['price']:,} | اینبوندها: {p.get('inbound_ids', 'پیش‌فرض') or 'پیش‌فرض'}")
            lines.append("")

    kb_rows = []
    for p in plans:
        status_icon = "🟢" if p.get("is_active") else "🔴"
        kb_rows.append([InlineKeyboardButton(
            text=f"{status_icon} {p['name']} — {p['gb']}GB/{p['days']}d",
            callback_data=f"adm_panel_plan_detail_{panel_id}_{p['id']}",
        )])
    kb_rows.append([InlineKeyboardButton(text="➕ افزودن پلن", callback_data=f"adm_panel_add_plan_{panel_id}")])
    kb_rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_detail_{panel_id}")])

    await callback.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_plan_detail_"))
async def cb_panel_plan_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    plan_id = int(parts[-1])
    import database as db
    plan = await db.get_plan(plan_id)
    panel = await db.get_panel(panel_id)
    if not plan or not panel:
        await callback.answer("یافت نشد!", show_alert=True)
        return

    status = "🟢 فعال" if plan.get("is_active") else "🔴 غیرفعال"
    ib_text = plan.get("inbound_ids") or "پیش‌فرض"
    ip_text = f"{plan.get('ip_limit', 0)}" if plan.get("ip_limit") else "بدون محدودیت"

    text = (
        f"📋 **جزئیات پلن: {plan['name']}**\n\n"
        f"📊 حجم: **{plan['gb']} GB**\n"
        f"📅 مدت: **{plan['days']} روز**\n"
        f"💰 قیمت: **{plan['price']:,}**\n"
        f"📡 اینبوندها: `{ib_text}`\n"
        f"🔒 محدودیت IP: {ip_text}\n"
        f"📈 وضعیت: {status}\n"
        f"🔗 پنل: {panel['name']}"
    )

    toggle_text = "🔴 غیرفعال کردن" if plan.get("is_active") else "🟢 فعال کردن"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"adm_panel_edit_plan_{panel_id}_{plan_id}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"adm_panel_toggle_plan_{panel_id}_{plan_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"adm_panel_delete_plan_{panel_id}_{plan_id}"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"adm_panel_plans_{panel_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_add_plan_"))
async def cb_panel_add_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    await state.update_data(panel_plan_panel_id=panel_id)
    await state.set_state(PanelState.waiting_panel_plan_name)
    import database as db
    panel = await db.get_panel(panel_id)
    text = (
        f"➕ **افزودن پلن به پنل: {panel['name']}** (مرحله ۱ از ۶)\n\n"
        "نام پلن را وارد کنید (مثال: `۱ ماهه ۵۰ گیگ`):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_plans_{panel_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.message(PanelState.waiting_panel_plan_name)
async def process_panel_plan_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("نام خیلی کوتاه است. حداقل ۲ کاراکتر.")
        return
    await state.update_data(panel_plan_name=name)
    await state.set_state(PanelState.waiting_panel_plan_gb)
    data = await state.get_data()
    panel_id = data["panel_plan_panel_id"]
    await message.answer(
        f"➕ **افزودن پلن: {name}** (مرحله ۲ از ۶)\n\n"
        "📊 حجم را به گیگابایت وارد کنید (مثال: `50`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_plans_{panel_id}")]
        ]),
    )


@panel_router.message(PanelState.waiting_panel_plan_gb)
async def process_panel_plan_gb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        gb = int(message.text.strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(panel_plan_gb=gb)
    await state.set_state(PanelState.waiting_panel_plan_days)
    data = await state.get_data()
    panel_id = data["panel_plan_panel_id"]
    await message.answer(
        f"➕ **افزودن پلن: {data['panel_plan_name']}** (مرحله ۳ از ۶)\n\n"
        "📅 مدت را به روز وارد کنید (مثال: `30`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_plans_{panel_id}")]
        ]),
    )


@panel_router.message(PanelState.waiting_panel_plan_days)
async def process_panel_plan_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(panel_plan_days=days)
    await state.set_state(PanelState.waiting_panel_plan_price)
    data = await state.get_data()
    panel_id = data["panel_plan_panel_id"]
    from database import get_setting
    symbol = await get_setting("currency_symbol") or "تومان"
    await message.answer(
        f"➕ **افزودن پلن: {data['panel_plan_name']}** (مرحله ۴ از ۶)\n\n"
        f"💰 قیمت را به {symbol} وارد کنید (مثال: `150000`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_plans_{panel_id}")]
        ]),
    )


@panel_router.message(PanelState.waiting_panel_plan_price)
async def process_panel_plan_price(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ قیمت نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(panel_plan_price=price)
    await state.set_state(PanelState.waiting_panel_plan_ip_limit)
    data = await state.get_data()
    panel_id = data["panel_plan_panel_id"]
    await message.answer(
        f"➕ **افزودن پلن: {data['panel_plan_name']}** (مرحله ۵ از ۶)\n\n"
        "🔒 حداکثر تعداد IP همزمان:\n(۰ = بدون محدودیت)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="0 — بدون محدودیت", callback_data=f"adm_panel_plan_ip_{panel_id}_0")],
            [InlineKeyboardButton(text="1", callback_data=f"adm_panel_plan_ip_{panel_id}_1")],
            [InlineKeyboardButton(text="2", callback_data=f"adm_panel_plan_ip_{panel_id}_2")],
            [InlineKeyboardButton(text="3", callback_data=f"adm_panel_plan_ip_{panel_id}_3")],
            [InlineKeyboardButton(text="5", callback_data=f"adm_panel_plan_ip_{panel_id}_5")],
        ]),
    )


@panel_router.callback_query(F.data.startswith("adm_panel_plan_ip_"))
async def cb_panel_plan_ip_limit(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    ip_limit = int(parts[-1])
    await _finalize_panel_plan(callback.message, state, panel_id, ip_limit)


@panel_router.message(PanelState.waiting_panel_plan_ip_limit)
async def process_panel_plan_ip_limit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        ip_limit = int(message.text.strip())
        if ip_limit < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ عدد نامعتبر. یک عدد غیرمنفی وارد کنید:")
        return
    data = await state.get_data()
    panel_id = data["panel_plan_panel_id"]
    await _finalize_panel_plan(message, state, panel_id, ip_limit)


async def _finalize_panel_plan(target, state: FSMContext, panel_id: int, ip_limit: int):
    data = await state.get_data()
    import database as db
    panel = await db.get_panel(panel_id)
    svc_type = "v2ray"
    if panel and panel.get("panel_type") == "wireguard":
        svc_type = "wireguard"
    elif panel and panel.get("panel_type") == "pasarguard":
        svc_type = "pasarguard"
    plan_id = await db.add_plan(
        name=data["panel_plan_name"],
        gb=data["panel_plan_gb"],
        days=data["panel_plan_days"],
        price=data["panel_plan_price"],
        inbound_ids="",
        ip_limit=ip_limit,
        panel_id=panel_id,
        service_type=svc_type,
    )
    await state.clear()
    from database import get_setting
    symbol = await get_setting("currency_symbol") or "تومان"
    panel = await db.get_panel(panel_id)
    await target.answer(
        f"✅ پلن **{data['panel_plan_name']}** برای پنل **{panel['name']}** ایجاد شد!\n\n"
        f"📊 حجم: {data['panel_plan_gb']} GB\n"
        f"📅 مدت: {data['panel_plan_days']} روز\n"
        f"💰 قیمت: {data['panel_plan_price']:,} {symbol}\n"
        f"🔒 محدودیت IP: {'بدون محدودیت' if ip_limit == 0 else ip_limit}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 پلن‌های پنل", callback_data=f"adm_panel_plans_{panel_id}")],
        ]),
    )


@panel_router.callback_query(F.data.startswith("adm_panel_edit_plan_"))
async def cb_panel_edit_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    plan_id = int(parts[-1])
    import database as db
    plan = await db.get_plan(plan_id)
    panel = await db.get_panel(panel_id)
    if not plan or not panel:
        await callback.answer("یافت نشد!", show_alert=True)
        return

    await state.update_data(panel_plan_edit_panel_id=panel_id, panel_plan_edit_plan_id=plan_id)
    await state.set_state(PanelState.waiting_panel_plan_edit)

    from database import get_setting
    symbol = await get_setting("currency_symbol") or "تومان"
    text = (
        f"✏️ **ویرایش پلن: {plan['name']}**\n\n"
        f"مقادیر جدید را به این فرمت وارد کنید:\n"
        f"<code>نام | حجم | روز | قیمت</code>\n\n"
        f"مثال: <code>۱ ماهه | 50 | 30 | 150000</code>\n\n"
        f"فعلی: <code>{plan['name']} | {plan['gb']} | {plan['days']} | {plan['price']}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"adm_panel_plan_detail_{panel_id}_{plan_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@panel_router.message(PanelState.waiting_panel_plan_edit)
async def process_panel_plan_edit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    panel_id = data["panel_plan_edit_panel_id"]
    plan_id = data["panel_plan_edit_plan_id"]

    parts = message.text.split("|")
    if len(parts) != 4:
        await message.answer("❌ فرمت نامعتبر. از فرمت `نام | حجم | روز | قیمت` استفاده کنید:")
        return

    name = parts[0].strip()
    try:
        gb = int(parts[1].strip())
        days = int(parts[2].strip())
        price = int(parts[3].strip())
        if gb <= 0 or days <= 0 or price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ اعداد نامعتبر. حجم، روز و قیمت باید اعداد مثبت باشند:")
        return

    import database as db
    await db.update_plan(plan_id, name=name, gb=gb, days=days, price=price)
    await state.clear()

    from database import get_setting
    symbol = await get_setting("currency_symbol") or "تومان"
    await message.answer(
        f"✅ پلن با موفقیت به‌روزرسانی شد!\n\n"
        f"نام: {name}\n"
        f"📊 حجم: {gb} GB\n"
        f"📅 مدت: {days} روز\n"
        f"💰 قیمت: {price:,} {symbol}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 پلن‌های پنل", callback_data=f"adm_panel_plans_{panel_id}")],
        ]),
    )


@panel_router.callback_query(F.data.startswith("adm_panel_toggle_plan_"))
async def cb_panel_toggle_plan(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    plan_id = int(parts[-1])
    import database as db
    plan = await db.get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return
    new_status = not plan.get("is_active", True)
    await db.update_plan(plan_id, is_active=new_status)
    status_text = "فعال" if new_status else "غیرفعال"
    await callback.answer(f"پلن {status_text} شد!", show_alert=True)
    await cb_panel_plan_detail(callback)


@panel_router.callback_query(F.data.startswith("adm_panel_delete_plan_"))
async def cb_panel_delete_plan(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    plan_id = int(parts[-1])
    import database as db
    plan = await db.get_plan(plan_id)
    panel = await db.get_panel(panel_id)
    if not plan or not panel:
        await callback.answer("یافت نشد!", show_alert=True)
        return

    text = f"⚠️ **آیا از حذف پلن «{plan['name']}» مطمئید؟**\n\nاین عمل قابل بازگشت نیست."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 بله، حذف شود", callback_data=f"adm_panel_del_plan_confirm_{panel_id}_{plan_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"adm_panel_plan_detail_{panel_id}_{plan_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@panel_router.callback_query(F.data.startswith("adm_panel_del_plan_confirm_"))
async def cb_panel_delete_plan_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    panel_id = int(parts[-2])
    plan_id = int(parts[-1])
    import database as db
    await db.delete_plan(plan_id)
    await callback.message.edit_text(
        "✅ **پلن با موفقیت حذف شد!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 پلن‌های پنل", callback_data=f"adm_panel_plans_{panel_id}")]
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Panel Enable/Disable ──────────────────────────────────────
@panel_router.callback_query(F.data.startswith("adm_toggle_panel_"))
async def cb_toggle_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    panel_id = int(callback.data.split("_")[-1])
    import database as db
    panel = await db.get_panel(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return
    new_status = 0 if panel.get("is_active", 1) else 1
    await db.update_panel(panel_id, is_active=new_status)
    if new_status == 0:
        await panel_manager.remove(panel_id)
    else:
        await panel_manager.load_all()
    status_text = "فعال" if new_status else "غیرفعال"
    await callback.answer(f"پنل {status_text} شد!", show_alert=True)
    await cb_panel_detail(callback)


# ─── Panel Manager Helper ──────────────────────────────────────
# Override load_all to use async database
_original_load_all = panel_manager.load_all

async def _patched_load_all():
    import database as db
    panels = await db.get_active_panels()
    panel_manager._instances.clear()
    panel_manager._default = None
    for p in panels:
        inbound_ids = [int(x.strip()) for x in (p.get("inbound_ids") or "").split(",") if x.strip().isdigit()]
        instance = __import__("api").PanelAPI(
            panel_url=p["url"],
            panel_user=p["username"],
            panel_pass=p["password"],
            sub_link_template=p.get("sub_link_template", ""),
            inbound_ids=inbound_ids,
            panel_id=p["id"],
        )
        panel_manager._instances[p["id"]] = instance
        if p.get("is_default"):
            panel_manager._default = instance
    if not panel_manager._default and panel_manager._instances:
        panel_manager._default = next(iter(panel_manager._instances.values()))
    if not panel_manager._default:
        panel_manager._default = panel_api

panel_manager.load_all = _patched_load_all


async def _load_panels_from_db():
    import database as db
    return await db.get_all_panels()

panel_manager._load_panels_from_db = _load_panels_from_db
