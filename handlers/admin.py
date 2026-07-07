from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    is_admin,
    get_pending_receipts,
    get_receipt,
    approve_receipt,
    reject_receipt,
    get_user,
    get_user_count,
    get_config_count,
    get_total_revenue,
    search_users,
    set_banned,
    set_setting,
    get_setting,
    add_admin,
    remove_admin,
    get_admins,
    get_user_configs,
    get_all_plans,
    get_plan,
    add_plan,
    update_plan,
    delete_plan,
    add_config,
    update_balance,
    delete_config,
    get_all_users,
)
from api import panel_api
from keyboards.admin import (
    admin_menu,
    receipt_actions,
    user_actions,
    admin_settings_menu,
    buttons_menu,
    plans_management_menu,
    plan_actions,
    manage_admins_menu,
    back_to_admin,
    user_config_list,
    config_detail_actions,
)
from utils.texts import (
    admin_stats,
    receipt_info,
    user_info,
    setting_updated,
    no_pending_receipts,
)

router = Router()

BUTTON_SETTINGS = {
    "edit_btn_wallet": "btn_wallet",
    "edit_btn_free_test": "btn_free_test",
    "edit_btn_buy_config": "btn_buy_config",
    "edit_btn_my_configs": "btn_my_configs",
    "edit_btn_topup": "btn_topup",
    "edit_btn_tx_history": "btn_tx_history",
    "edit_btn_back": "btn_back",
    "edit_btn_back_to_menu": "btn_back_to_menu",
    "edit_btn_admin_stats": "btn_admin_stats",
    "edit_btn_admin_receipts": "btn_admin_receipts",
    "edit_btn_admin_users": "btn_admin_users",
    "edit_btn_admin_settings": "btn_admin_settings",
    "edit_btn_admin_admins": "btn_admin_admins",
    "edit_btn_admin_plans": "btn_admin_plans",
}


class AdminState(StatesGroup):
    edit_welcome = State()
    search_user = State()
    add_admin_id = State()
    remove_admin_id = State()
    edit_button_name = State()
    edit_currency = State()
    edit_card_number = State()
    edit_card_owner = State()
    waiting_emoji_name = State()
    waiting_emoji_id = State()
    add_plan_name = State()
    add_plan_gb = State()
    add_plan_days = State()
    add_plan_price = State()
    edit_plan_field = State()
    edit_free_test_mb = State()
    add_balance = State()
    remove_balance = State()
    broadcast = State()
    edit_auto_approve = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("شما ادمین نیستید.")
        return
    await message.answer("<b>پنل ادمین</b>", reply_markup=await admin_menu())


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    try:
        await callback.message.edit_text("<b>پنل ادمین</b>", reply_markup=await admin_menu())
    except Exception:
        await callback.message.answer("<b>پنل ادمین</b>", reply_markup=await admin_menu())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    user_count = await get_user_count()
    config_count = await get_config_count()
    revenue = await get_total_revenue()
    pending = len(await get_pending_receipts())

    text = await admin_stats(user_count, config_count, revenue, pending, symbol)
    await callback.message.edit_text(text, reply_markup=await back_to_admin())


@router.callback_query(F.data == "pending_receipts")
async def cb_pending_receipts(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    receipts = await get_pending_receipts()
    if not receipts:
        await callback.message.edit_text(await no_pending_receipts(), reply_markup=await back_to_admin())
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    text = "**Pending Receipts**\n\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for r in receipts[:10]:
        text += f"#{r['id']} - @{r.get('username', 'N/A')} - {r['amount']:,.0f} {symbol}\n"
        buttons.append([InlineKeyboardButton(
            text=f"#{r['id']} - {r['amount']:,.0f} {symbol}",
            callback_data=f"view_receipt_{r['id']}",
        )])
    btn_back = await get_setting("btn_back")
    buttons.append([InlineKeyboardButton(text=btn_back, callback_data="admin_menu")])

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("view_receipt_"))
async def cb_view_receipt(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("رسید یافت نشد!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    text = await receipt_info(receipt, symbol)
    user = await get_user(receipt["user_id"])
    if user:
        text += f"\n\nموجودی: {user['balance']:,.0f} {symbol}"
    if receipt.get("plan_id") and receipt["plan_id"] > 0:
        plan = await get_plan(receipt["plan_id"])
        if plan:
            text += f"\n\n<b>پلن:</b> {plan['name']} ({plan['gb']}GB / {plan['days']} روز)"
            text += f"\n**Type:** Card-to-Card"

    await callback.message.delete()
    await callback.message.answer_photo(
        photo=receipt["photo_file_id"],
        caption=text,
        parse_mode="Markdown",
        reply_markup=await receipt_actions(receipt_id),
    )


@router.callback_query(F.data.startswith("approve_"))
async def cb_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("رسید یافت نشد!", show_alert=True)
        return

    await approve_receipt(receipt_id, callback.from_user.id)
    symbol = await get_setting("currency_symbol") or "تومان"

    try:
        await callback.message.edit_caption(
            caption=f"**Receipt #{receipt_id} Approved**",
            parse_mode="Markdown",
            reply_markup=await back_to_admin(),
        )
    except Exception:
        pass

    try:
        if receipt["plan_id"] and receipt["plan_id"] > 0:
            from aiogram.types import InlineKeyboardMarkup
            from keyboards.user import _btn
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [await _btn("ساخت کانفیگ من", f"make_config_{receipt['plan_id']}", "package", btn_id="make_config")],
            ])
            await callback.bot.send_message(
                chat_id=receipt["user_id"],
                text=f"Transfer successful! ({receipt['amount']:,.0f} {symbol})\n\nClick below to get your config:",
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


@router.callback_query(F.data.startswith("reject_"))
async def cb_reject(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    receipt_id = int(callback.data.split("_")[-1])
    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("رسید یافت نشد!", show_alert=True)
        return

    await reject_receipt(receipt_id, callback.from_user.id)

    await callback.message.edit_caption(
        caption=f"**Receipt #{receipt_id} Rejected**",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )

    try:
        from utils.texts import receipt_rejected
        symbol = await get_setting("currency_symbol") or "تومان"
        await callback.bot.send_message(
            chat_id=receipt["user_id"],
            text=await receipt_rejected(receipt["amount"], symbol),
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.search_user)
    await callback.message.edit_text(
        "**User Management**\n\nEnter user ID or username to search:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.message(F.text, AdminState.search_user)
async def process_search_user(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()

    users = await search_users(message.text.strip())
    if not users:
        await message.answer("کاربری یافت نشد.", reply_markup=await back_to_admin())
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for u in users[:10]:
        buttons.append([InlineKeyboardButton(
            text=f"@{u.get('username', 'N/A')} ({u['id']}) - {u['balance']:,.0f}",
            callback_data=f"view_user_{u['id']}",
        )])
    btn_back = await get_setting("btn_back")
    buttons.append([InlineKeyboardButton(text=btn_back, callback_data="admin_menu")])

    await message.answer(
        f"**Search Results** ({len(users)} found)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("view_user_"))
async def cb_view_user(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    user = await get_user(user_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    configs = await get_user_configs(user_id)
    text = await user_info(user, symbol)
    text += f"\nکانفیگ‌ها: {len(configs)}"

    await callback.message.edit_text(text, reply_markup=await user_actions(user_id))


@router.callback_query(F.data.startswith("ban_"))
async def cb_ban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    await set_banned(user_id, True)
    await callback.answer("کاربر مسدود شد!", show_alert=True)
    await cb_view_user(callback)


@router.callback_query(F.data.startswith("unban_"))
async def cb_unban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    await set_banned(user_id, False)
    await callback.answer("کاربر از مسدودی خارج شد!", show_alert=True)
    await cb_view_user(callback)


@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await callback.message.edit_text("**Bot Settings**", parse_mode="Markdown", reply_markup=await admin_settings_menu())


@router.callback_query(F.data == "edit_welcome")
async def cb_edit_welcome(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.edit_welcome)
    await callback.message.edit_text(
        "متن خوش‌آمدگویی جدید را وارد کنید:",
        reply_markup=await back_to_admin(),
    )


@router.message(AdminState.edit_welcome)
async def process_edit_welcome(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("welcome_text", message.text)
    await state.clear()
    await message.answer(await setting_updated("Welcome Text", message.text[:100]), reply_markup=await back_to_admin())


@router.callback_query(F.data == "edit_buttons")
async def cb_edit_buttons(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await callback.message.edit_text(
        "**Edit Button Names**\n\nClick a button to change its text:",
        parse_mode="Markdown",
        reply_markup=await buttons_menu(),
    )


@router.callback_query(F.data.startswith("edit_btn_"))
async def cb_edit_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    setting_key = BUTTON_SETTINGS.get(callback.data)
    if not setting_key:
        await callback.answer("Unknown button!", show_alert=True)
        return

    current = await get_setting(setting_key) or ""
    await state.update_data(button_key=setting_key)
    await state.set_state(AdminState.edit_button_name)
    await callback.message.edit_text(
        f"Current text: **{current}**\n\nEnter new button text:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
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
    await message.answer(
        f"Button updated to: **{message.text}**",
        parse_mode="Markdown",
        reply_markup=await buttons_menu(),
    )


@router.callback_query(F.data == "edit_currency")
async def cb_edit_currency(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.edit_currency)
    await callback.message.edit_text(
        f"Current currency symbol: **{current}**\n\nEnter new currency symbol (e.g., تومان, IRR, $):",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.message(AdminState.edit_currency)
async def process_edit_currency(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("currency_symbol", message.text)
    await state.clear()
    await message.answer(
        f"Currency symbol updated to: **{message.text}**",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.callback_query(F.data == "edit_card_number")
async def cb_edit_card_number(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("card_number") or ""
    await state.set_state(AdminState.edit_card_number)
    await callback.message.edit_text(
        f"Current card number: `{current}`\n\nEnter new card number:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.message(AdminState.edit_card_number)
async def process_edit_card_number(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("card_number", message.text)
    await state.clear()
    await message.answer(
        f"Card number updated to: `{message.text}`",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.callback_query(F.data == "edit_card_owner")
async def cb_edit_card_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("card_owner") or ""
    await state.set_state(AdminState.edit_card_owner)
    await callback.message.edit_text(
        f"Current card owner: **{current}**\n\nEnter new card owner name:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.message(AdminState.edit_card_owner)
async def process_edit_card_owner(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await set_setting("card_owner", message.text)
    await state.clear()
    await message.answer(
        f"Card owner updated to: **{message.text}**",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.callback_query(F.data == "edit_free_test_mb")
async def cb_edit_free_test_mb(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("free_test_mb") or "102400"
    await state.set_state(AdminState.edit_free_test_mb)
    await callback.message.edit_text(
        f"Current free test volume: **{current} MB**\n\nEnter new volume in MB:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
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
        await message.answer("عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await set_setting("free_test_mb", str(mb))
    await state.clear()
    await message.answer(
        f"Free test volume updated to: **{mb} MB**",
        parse_mode="Markdown",
        reply_markup=await admin_settings_menu(),
    )


@router.callback_query(F.data == "toggle_free_test")
async def cb_toggle_free_test(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("free_test_enabled") or "1"
    new_value = "0" if current == "1" else "1"
    await set_setting("free_test_enabled", new_value)
    status = "enabled" if new_value == "1" else "disabled"
    await callback.answer(f"Free test {status}!", show_alert=True)
    await callback.message.edit_text("**Bot Settings**", parse_mode="Markdown", reply_markup=await admin_settings_menu())


@router.callback_query(F.data == "edit_auto_approve")
async def cb_edit_auto_approve(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    current = await get_setting("auto_approve_max") or "0"
    symbol = await get_setting("currency_symbol") or "تومان"
    status = f"{float(current):,.0f} {symbol}" if float(current) > 0 else "Disabled"
    await state.set_state(AdminState.edit_auto_approve)
    await callback.message.edit_text(
        f"**Auto-Approve Receipts**\n\n"
        f"Current limit: **{status}**\n\n"
        f"Receipts at or below this amount are auto-approved.\n"
        f"Enter 0 to disable, or enter the threshold in {symbol}:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
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
        await message.answer("عدد نامعتبر. یک عدد مثبت یا 0 وارد کنید:")
        return
    await set_setting("auto_approve_max", str(amount))
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    if amount > 0:
        text = f"Auto-approve set to **{amount:,.0f} {symbol}**"
    else:
        text = "Auto-approve **disabled**"
    await message.answer(text, parse_mode="Markdown", reply_markup=await admin_settings_menu())


@router.callback_query(F.data == "edit_premium_emojis")
async def cb_edit_premium_emojis(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    from keyboards.admin import premium_emojis_menu
    await callback.message.edit_text(
        "**Premium Emojis**\n\n"
        "Register premium emojis by sending them here.\n"
        "Each emoji will be linked to a button name.\n\n"
        "Bot sends messages with these emojis using Telegram's premium emoji system.",
        parse_mode="Markdown",
        reply_markup=await premium_emojis_menu(),
    )


@router.callback_query(F.data == "send_emoji_register")
async def cb_send_emoji_register(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    from keyboards.admin import premium_emojis_menu
    await callback.message.edit_text(
        "**Register Premium Emoji**\n\n"
        "First send the emoji name (e.g., `wallet`),\n"
        "then send the premium emoji in the next message.",
        parse_mode="Markdown",
        reply_markup=await premium_emojis_menu(),
    )
    await state.set_state(AdminState.waiting_emoji_name)


@router.message(F.text, F.text.contains(" "), AdminState.edit_welcome)
async def process_emoji_register(message: Message, state: FSMContext):
    pass


@router.message(AdminState.waiting_emoji_name)
async def process_emoji_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    valid_names = [
        "wallet", "free_test", "buy_config", "my_configs", "back", "admin",
        "stats", "users", "settings", "plans", "receipts", "admins", "check", "cross",
        "card", "owner", "star", "copy", "cancel", "success", "approve", "reject",
        "ban", "unban", "plus", "minus", "list", "gear", "money", "calendar", "history", "menu",
        "package", "link", "clock", "start", "copy_number", "copy_price",
    ]
    name = message.text.strip().lower()
    if name not in valid_names:
        await message.answer(
            f"Invalid name. Use one of: {', '.join(valid_names)}",
        )
        return
    await state.update_data(emoji_name=name)
    await state.set_state(AdminState.waiting_emoji_id)
    await message.answer(
        f"Name: **{name}**\n\nNow send the premium emoji.",
        parse_mode="Markdown",
    )


@router.message(AdminState.waiting_emoji_id)
async def process_emoji_receive(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    emoji_name = data.get("emoji_name", "")
    if not emoji_name:
        await state.clear()
        await message.answer("Something went wrong. Start again from Settings > Premium Emojis.")
        return

    for entity in (message.entities or []) + (message.caption_entities or []):
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            from utils.premium_emoji import register_premium_emoji
            await register_premium_emoji(emoji_name, entity.custom_emoji_id)
            await state.clear()
            await message.answer(
                f"Emoji registered: **{emoji_name}** -> `{entity.custom_emoji_id}`",
                parse_mode="Markdown",
            )
            return

    await state.clear()
    await message.answer(
        "No premium emoji found. Send a message containing a premium emoji.",
    )


@router.callback_query(F.data == "view_emojis")
async def cb_view_emojis(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    from utils.premium_emoji import load_emoji_ids
    from keyboards.admin import premium_emojis_menu
    mapping = await load_emoji_ids()
    if not mapping:
        text = "**Registered Emojis**\n\nNo premium emojis registered yet."
    else:
        text = "**Registered Emojis**\n\n"
        for name, eid in mapping.items():
            text += f"  {name}: `{eid}`\n"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await premium_emojis_menu())


@router.callback_query(F.data == "clear_emojis")
async def cb_clear_emojis(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    from utils.premium_emoji import save_emoji_ids
    from keyboards.admin import premium_emojis_menu
    await save_emoji_ids({})
    await callback.answer("همه ایموجی‌ها پاک شدند!", show_alert=True)
    await callback.message.edit_text(
        "**Premium Emojis**\n\nAll registered emojis have been cleared.",
        parse_mode="Markdown",
        reply_markup=await premium_emojis_menu(),
    )


@router.callback_query(F.data == "admin_plans")
async def cb_admin_plans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await callback.message.edit_text("**Plans Management**", parse_mode="Markdown", reply_markup=await plans_management_menu())


@router.callback_query(F.data.startswith("plan_detail_"))
async def cb_plan_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    status = "Active" if plan["is_active"] else "Deleted"
    text = (
        f"**{plan['name']}**\n\n"
        f"Volume: {plan['gb']}GB\n"
        f"Duration: {plan['days']} days\n"
        f"Price: {plan['price']:,} {symbol}\n"
        f"Status: {status}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await plan_actions(plan_id))


@router.callback_query(F.data == "add_plan")
async def cb_add_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.add_plan_name)
    await callback.message.edit_text("نام پلن را وارد کنید (مثال: 1 ماهه):", reply_markup=await back_to_admin())


@router.message(AdminState.add_plan_name)
async def process_plan_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.update_data(plan_name=message.text)
    await state.set_state(AdminState.add_plan_gb)
    await message.answer("حجم را به گیگابایت وارد کنید (مثال: 50):")


@router.message(AdminState.add_plan_gb)
async def process_plan_gb(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        gb = int(message.text.strip())
        if gb <= 0:
            raise ValueError
    except ValueError:
        await message.answer("عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(plan_gb=gb)
    await state.set_state(AdminState.add_plan_days)
    await message.answer("مدت را به روز وارد کنید (مثال: 30):")


@router.message(AdminState.add_plan_days)
async def process_plan_days(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("عدد نامعتبر. یک عدد مثبت وارد کنید:")
        return
    await state.update_data(plan_days=days)
    symbol = await get_setting("currency_symbol") or "تومان"
    await state.set_state(AdminState.add_plan_price)
    await message.answer(f"Enter price in {symbol} (e.g., 150000):")


@router.message(AdminState.add_plan_price)
async def process_plan_price(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("قیمت نامعتبر. یک عدد مثبت وارد کنید:")
        return
    data = await state.get_data()
    await add_plan(data["plan_name"], data["plan_gb"], data["plan_days"], price)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    await message.answer(
        f"Plan created: **{data['plan_name']}** | {data['plan_gb']}GB | {data['plan_days']}D | {price:,} {symbol}",
        parse_mode="Markdown",
        reply_markup=await plans_management_menu(),
    )


@router.callback_query(F.data.startswith("edit_plan_"))
async def cb_edit_plan(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    await state.update_data(edit_plan_id=plan_id)
    await state.set_state(AdminState.edit_plan_field)
    await callback.message.edit_text(
        f"**Editing: {plan['name']}**\n\n"
        f"Reply with the new values in this format:\n"
        f"`name | gb | days | price`\n\n"
        f"Example: `1 Month | 50 | 30 | 150000`\n"
        f"Current: `{plan['name']} | {plan['gb']} | {plan['days']} | {plan['price']}`",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.message(AdminState.edit_plan_field)
async def process_edit_plan(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    plan_id = data.get("edit_plan_id")
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 4:
            raise ValueError
        name = parts[0]
        gb = int(parts[1])
        days = int(parts[2])
        price = int(parts[3])
        if gb <= 0 or days <= 0 or price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Invalid format. Use: `name | gb | days | price`", parse_mode="Markdown")
        return

    await update_plan(plan_id, name=name, gb=gb, days=days, price=price)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"
    await message.answer(
        f"Plan updated: **{name}** | {gb}GB | {days}D | {price:,} {symbol}",
        parse_mode="Markdown",
        reply_markup=await plans_management_menu(),
    )


@router.callback_query(F.data.startswith("delete_plan_"))
async def cb_delete_plan(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    plan_id = int(callback.data.split("_")[-1])
    await delete_plan(plan_id)
    await callback.answer("Plan deleted!", show_alert=True)
    await callback.message.edit_text("**Plans Management**", parse_mode="Markdown", reply_markup=await plans_management_menu())


@router.callback_query(F.data == "manage_admins")
async def cb_manage_admins(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await callback.message.edit_text("**Admin Management**", parse_mode="Markdown", reply_markup=await manage_admins_menu())


@router.callback_query(F.data == "list_admins")
async def cb_list_admins(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    admins = await get_admins()
    text = "**Admins**\n\n"
    for a in admins:
        text += f"@{a.get('username', 'N/A')} (ID: {a['user_id']})\n"

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await manage_admins_menu())


@router.callback_query(F.data == "add_admin")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.add_admin_id)
    await callback.message.edit_text("Enter the Telegram user ID to add as admin:", reply_markup=await back_to_admin())


@router.message(AdminState.add_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("آیدی نامعتبر. یک آیدی عددی تلگرام وارد کنید:")
        return
    await add_admin(user_id, None)
    await state.clear()
    await message.answer(f"Admin {user_id} added!", reply_markup=await back_to_admin())


@router.callback_query(F.data == "remove_admin")
async def cb_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.remove_admin_id)
    await callback.message.edit_text("Enter the Telegram user ID to remove from admins:", reply_markup=await back_to_admin())


@router.message(AdminState.remove_admin_id)
async def process_remove_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("آیدی نامعتبر. یک آیدی عددی تلگرام وارد کنید:")
        return

    if user_id == message.from_user.id:
        await message.answer("نتوانید خودتان را حذف کنید!", reply_markup=await back_to_admin())
        return

    await remove_admin(user_id)
    await state.clear()
    await message.answer(f"Admin {user_id} removed!", reply_markup=await back_to_admin())


@router.callback_query(F.data.startswith("admin_cfgs_"))
async def cb_user_configs_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    user = await get_user(user_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    configs = await get_user_configs(user_id)
    if not configs:
        await callback.answer("No configs found for this user.", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    text = f"**Configs for @{user.get('username', 'N/A')}**\n\n"
    for c in configs[:10]:
        status = "\u2705" if c["is_active"] else "\u274c"
        text += f"{status} #{c['id']} | {c['email']} | Exp: {c['expire_date'][:10]}\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=await user_config_list(configs, user_id),
    )


@router.callback_query(F.data.startswith("admin_cfg_"))
async def cb_config_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    parts = callback.data.split("_")
    config_id = int(parts[2])
    user_id = int(parts[3])

    from database import get_db
    db = await get_db()
    cursor = await db.execute("SELECT * FROM configs WHERE id = ?", (config_id,))
    cfg = await cursor.fetchone()
    await db.close()

    if not cfg:
        await callback.answer("کانفیگ یافت نشد!", show_alert=True)
        return

    cfg = dict(cfg)
    status = "Active" if cfg["is_active"] else "Expired"
    text = (
        f"**Config #{cfg['id']}** ({status})\n\n"
        f"Email: `{cfg['email']}`\n"
        f"Link: `{cfg['sub_link']}`\n"
        f"Expires: {cfg['expire_date'][:10]}"
    )
    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=await config_detail_actions(config_id, user_id),
    )


@router.callback_query(F.data.startswith("admin_del_cfg_"))
async def cb_delete_config(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    parts = callback.data.split("_")
    config_id = int(parts[3])
    user_id = int(parts[4])

    await delete_config(config_id)
    await callback.answer("Config deleted!", show_alert=True)

    configs = await get_user_configs(user_id)
    if not configs:
        user = await get_user(user_id)
        symbol = await get_setting("currency_symbol") or "تومان"
        text = f"**Configs for @{user.get('username', 'N/A')}**\n\nNo configs left."
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await back_to_admin())
        return

    user = await get_user(user_id)
    symbol = await get_setting("currency_symbol") or "تومان"
    text = f"**Configs for @{user.get('username', 'N/A')}**\n\n"
    for c in configs[:10]:
        status = "\u2705" if c["is_active"] else "\u274c"
        text += f"{status} #{c['id']} | {c['email']} | Exp: {c['expire_date'][:10]}\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=await user_config_list(configs, user_id),
    )


@router.callback_query(F.data.startswith("add_bal_"))
async def cb_add_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    await state.update_data(bal_user_id=user_id)
    await state.set_state(AdminState.add_balance)
    symbol = await get_setting("currency_symbol") or "تومان"
    await callback.message.edit_text(
        f"**Add Balance**\n\nEnter amount in {symbol}:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
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
        await message.answer("Invalid amount. Enter a positive number:")
        return

    data = await state.get_data()
    user_id = data.get("bal_user_id")
    await update_balance(user_id, amount)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    new_balance = user["balance"] if user else 0
    await message.answer(
        f"\u2705 Added **{amount:,.0f} {symbol}** to user `{user_id}`\n"
        f"New balance: **{new_balance:,.0f} {symbol}**",
        parse_mode="Markdown",
        reply_markup=await user_actions(user_id),
    )


@router.callback_query(F.data.startswith("rem_bal_"))
async def cb_remove_balance(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    await state.update_data(bal_user_id=user_id)
    await state.set_state(AdminState.remove_balance)
    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    balance = user["balance"] if user else 0
    await callback.message.edit_text(
        f"**Remove Balance**\n\nCurrent balance: **{balance:,.0f} {symbol}**\n\nEnter amount to remove:",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
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
        await message.answer("Invalid amount. Enter a positive number:")
        return

    data = await state.get_data()
    user_id = data.get("bal_user_id")
    user = await get_user(user_id)
    current = user["balance"] if user else 0

    if amount > current:
        await message.answer(
            f"Cannot remove {amount:,.0f} — user only has {current:,.0f}. Enter a smaller amount:"
        )
        return

    await update_balance(user_id, -amount)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(user_id)
    new_balance = user["balance"] if user else 0
    await message.answer(
        f"\u2705 Removed **{amount:,.0f} {symbol}** from user `{user_id}`\n"
        f"New balance: **{new_balance:,.0f} {symbol}**",
        parse_mode="Markdown",
        reply_markup=await user_actions(user_id),
    )


@router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    await state.set_state(AdminState.broadcast)
    await callback.message.edit_text(
        "**Broadcast Message**\n\nSend the message you want to broadcast to all users. "
        "Supports HTML formatting.",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )


@router.callback_query(F.data == "panel_info")
async def cb_panel_info(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    import os
    web_port = os.getenv("WEB_PORT", "5000")
    admin_user = os.getenv("ADMIN_WEB_USER", "admin")
    admin_pass = os.getenv("ADMIN_WEB_PASS", "changeme")
    text = (
        f"**Dashboard Info**\n\n"
        f"URL: `http://YOUR_IP:{web_port}`\n"
        f"Username: `{admin_user}`\n"
        f"Password: `{admin_pass}`\n\n"
        f"Replace YOUR_IP with your server IP."
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await back_to_admin())


@router.message(AdminState.broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.clear()
    users = await get_all_users()
    total = len(users)
    sent = 0
    failed = 0

    await message.answer(f"Broadcasting to {total} users...")

    for user in users:
        try:
            await message.bot.send_message(
                chat_id=user["id"],
                text=message.html_text if message.html_text else message.text,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"**Broadcast Complete**\n\n"
        f"\u2705 Sent: {sent}\n"
        f"\u274c Failed: {failed}\n"
        f"\U0001f465 Total: {total}",
        parse_mode="Markdown",
        reply_markup=await back_to_admin(),
    )
