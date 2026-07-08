from aiogram import Router, F, BaseMiddleware
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import time
from database import (
    add_user, get_user, get_user_configs, has_free_test, add_config,
    get_setting, is_admin, get_plan, add_receipt, get_admins, update_balance,
    get_config_by_id, update_config_sub_link, get_plan_name,
)
from api import panel_api
from keyboards.user import (
    main_menu, back_to_menu, plans_menu, payment_method_menu, config_detail,
    force_join_keyboard, service_detail_keyboard, extra_volume_keyboard,
    regenerate_link_keyboard, sections_menu,
)
from utils.texts import (
    WELCOME_TEXT_DEFAULT, config_list_text, config_created, free_test_config, no_balance,
    service_list_text, service_detail_text, buy_extra_volume_text, extra_volume_success_text,
    no_balance_for_extra, regenerate_link_confirm_text, regenerate_link_success_text,
    volume_detail_text, extract_configs_text,
)
from utils.premium_emoji import pe, get_button_emoji_id
from utils.qr_generator import generate_qr

router = Router()

TEST_CONFIG_DAYS = 1


async def _is_channel_member(bot, user_id: int) -> bool:
    enabled = await get_setting("force_join_enabled")
    if enabled != "1":
        return True
    channel_id = await get_setting("required_channel_id")
    if not channel_id:
        return True
    if not channel_id.startswith("@") and not channel_id.startswith("-"):
        channel_id = "@" + channel_id
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True


async def _send_force_join(bot, chat_id: int):
    channel_id = await get_setting("required_channel_id") or ""
    text = await get_setting("force_join_text") or "⚠️ برای استفاده از ربات، ابتدا باید در کانال ما عضو شوید!"
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=await force_join_keyboard(channel_id))


async def _notify_new_user(bot, user):
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        return
    try:
        from database import get_user_count_by_period
        today = await get_user_count_by_period(1)
        week = await get_user_count_by_period(7)
        month = await get_user_count_by_period(30)
        lifetime = await get_user_count_by_period(0)
        username = f"@{user.username}" if user.username else "ندارد"

        tpl = await get_setting("text_new_user_notification") or (
            "🆕 <b>کاربر جدید ربات را استارت کرد!</b>\n\n"
            "  👤 نام کاربری: {username}\n"
            "  🔢 آیدی عددی: <code>{user_id}</code>\n"
            "  📛 نام: {first_name}\n\n"
            "  📊 آمار کاربران:\n"
            "     امروز: <b>{today}</b>\n"
            "     ۷ روز: <b>{week}</b>\n"
            "     ۳۰ روز: <b>{month}</b>\n"
            "     کل: <b>{lifetime}</b>"
        )

        text = tpl.replace("{username}", username) \
            .replace("{user_id}", str(user.id)) \
            .replace("{first_name}", user.first_name or "ندارد") \
            .replace("{today}", str(today)) \
            .replace("{week}", str(week)) \
            .replace("{month}", str(month)) \
            .replace("{lifetime}", str(lifetime))

        await bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML")
    except Exception:
        pass


async def _send_receipt_to_channel(bot, photo_file_id, caption: str, receipt_id: int = 0):
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        return
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from keyboards.user import _btn
        kb = None
        if receipt_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    await _btn("تایید", f"channel_approve_{receipt_id}", btn_id="approve"),
                    await _btn("رد", f"channel_reject_{receipt_id}", btn_id="reject"),
                ]
            ])
        await bot.send_photo(chat_id=channel_id, photo=photo_file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        pass


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: CallbackQuery, data: dict):
        if event.data == "check_membership":
            return await handler(event, data)
        if not await _is_channel_member(event.bot, event.from_user.id):
            fail_text = await get_setting("force_join_fail_text") or "⚠️ ابتدا در کانال عضو شوید!"
            await event.answer(fail_text, show_alert=True)
            return
        return await handler(event, data)


router.callback_query.middleware(ForceJoinMiddleware())


async def _start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="▶️ شروع")]],
        resize_keyboard=True,
    )


class C2CState(StatesGroup):
    waiting_confirm = State()
    waiting_photo = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    invite_code = args[1] if len(args) > 1 else None

    is_new = await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if is_new:
        if invite_code:
            from database import get_user_by_invite_code, set_referred_by
            referrer = await get_user_by_invite_code(invite_code)
            if referrer and referrer["id"] != message.from_user.id:
                await set_referred_by(message.from_user.id, referrer["id"])
        await _notify_new_user(message.bot, message.from_user)
    if not await _is_channel_member(message.bot, message.from_user.id):
        await _send_force_join(message.bot, message.from_user.id)
        return
    welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
    await message.answer(welcome, parse_mode="HTML", reply_markup=await _start_kb())
    menu_msg = await message.answer("منوی اصلی", reply_markup=await main_menu(message.from_user.id))
    try:
        await message.bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[{"type": "emoji", "emoji": "🔥"}],
        )
    except Exception:
        pass


@router.message(F.text == "▶️ شروع")
async def btn_start(message: Message):
    is_new = await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if is_new:
        await _notify_new_user(message.bot, message.from_user)
    if not await _is_channel_member(message.bot, message.from_user.id):
        await _send_force_join(message.bot, message.from_user.id)
        return
    welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
    menu_msg = await message.answer(welcome, parse_mode="HTML", reply_markup=await main_menu(message.from_user.id))
    try:
        await message.bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[{"type": "emoji", "emoji": "🔥"}],
        )
    except Exception:
        pass


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(callback: CallbackQuery):
    if await _is_channel_member(callback.bot, callback.from_user.id):
        try:
            await callback.message.delete()
        except Exception:
            pass
        welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
        await callback.message.answer(welcome, parse_mode="HTML", reply_markup=await _start_kb())
        menu_msg = await callback.message.answer("منوی اصلی", reply_markup=await main_menu(callback.from_user.id))
        try:
            await callback.bot.set_message_reaction(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reaction=[{"type": "emoji", "emoji": "🔥"}],
            )
        except Exception:
            pass
    else:
        fail_text = await get_setting("force_join_fail_text") or "❌ شما هنوز در کانال عضو نیستید! لطفاً ابتدا عضو شوید و سپس دوباره بررسی کنید."
        await callback.answer(fail_text, show_alert=True)


@router.callback_query(F.data == "invite")
async def cb_invite(callback: CallbackQuery):
    from database import get_invite_stats, get_setting
    enabled = await get_setting("invite_enabled")
    if enabled != "1":
        await callback.answer("این قابلیت غیرفعال است", show_alert=True)
        return
    stats = await get_invite_stats(callback.from_user.id)
    code = stats["code"] or "N/A"
    count = stats["count"]
    reward = await get_setting("invite_reward_amount") or "0"
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    text = (
        f"👥 <b>زیر مجموعه گیری</b>\n\n"
        f"لینک دعوت شما:\n<code>{link}</code>\n\n"
        f"تعداد زیرمجموعه‌ها: <b>{count}</b>\n"
        f"پاداش هر زیرمجموعه: <b>{reward} تومان</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("منوی اصلی", reply_markup=await main_menu(message.from_user.id))


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("منوی اصلی", reply_markup=await main_menu(callback.from_user.id))
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("منوی اصلی", reply_markup=await main_menu(callback.from_user.id))


@router.callback_query(F.data == "free_test")
async def cb_free_test(callback: CallbackQuery):
    user_id = callback.from_user.id
    free_test_enabled = await get_setting("free_test_enabled")
    if free_test_enabled != "1":
        await callback.answer("Free test is currently disabled.", show_alert=True)
        return
    admin = await is_admin(user_id)
    if not admin and await has_free_test(user_id):
        await callback.answer("You already used your free test!", show_alert=True)
        return

    user = await get_user(user_id)
    if not user:
        await callback.answer("لطفاً ابتدا /start را بزنید", show_alert=True)
        return

    username = user.get("username") or str(user_id)
    ts = int(time.time())
    suffix = f"_{user_id}_{ts}" if admin else f"_test_{user_id}_{username}_{ts}"
    email = f"free{suffix}"

    await callback.answer("در حال ساخت کانفیگ رایگان...", show_alert=False)
    free_test_mb = int(await get_setting("free_test_mb") or "102400")
    result = await panel_api.create_test_config(email, total_mb=free_test_mb)
    if not result:
        await callback.message.edit_text(
            "ساخت کانفیگ ناموفق بود. لطفاً با ادمین تماس بگیرید.", reply_markup=await back_to_menu()
        )
        return

    await add_config(
        user_id=user_id,
        plan_id=0,
        sub_link=result["sub_link"],
        uuid=result["uuid"],
        email=email,
        expire_date=result["expire_date"],
    )

    text = await free_test_config(result["sub_link"], TEST_CONFIG_DAYS)
    qr_img = generate_qr(result["sub_link"])

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
    )

    # Notify admin channel
    channel_id = await get_setting("notification_channel_id") or ""
    if channel_id:
        try:
            user_display = f"@{username}" if username and not username.isdigit() else str(user_id)
            notif_text = (
                f"**کانفیگ رایگان ساخته شد!**\n\n"
                f"**کاربر:** {user_display} (ID: {user_id})\n"
                f"**حجم:** {free_test_mb // 1024} GB\n"
                f"**مدت:** {TEST_CONFIG_DAYS} روز\n\n"
                f"**لینک اشتراک:**\n`{result['sub_link']}`"
            )
            await callback.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data.startswith("make_config_"))
async def cb_make_config(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    username = user.get("username") or str(user_id)
    email = f"c2c_{user_id}_{username}_{int(time.time())}"

    await callback.answer("در حال ساخت کانفیگ...", show_alert=False)
    plan_inbound_ids = None
    if plan.get("inbound_ids"):
        plan_inbound_ids = [int(x.strip()) for x in plan["inbound_ids"].split(",") if x.strip().isdigit()]
    result = await panel_api.create_config(email, days=plan["days"], total_gb=plan["gb"], inbound_ids=plan_inbound_ids)
    if not result:
        await callback.message.edit_text("ساخت کانفیگ ناموفق بود. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
        return

    await add_config(
        user_id=user_id, plan_id=plan_id, sub_link=result["sub_link"],
        uuid=result["uuid"], email=email, expire_date=result["expire_date"],
    )

    await update_balance(user_id, -plan["price"])

    symbol = await get_setting("currency_symbol") or "تومان"
    text = await config_created(
        result["sub_link"], result["expire_date"][:10],
        plan["price"], plan["name"], plan["gb"], plan["days"], symbol,
    )
    qr_img = generate_qr(result["sub_link"])

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
    )

    # Notify admin channel
    channel_id = await get_setting("notification_channel_id") or ""
    if channel_id:
        try:
            user_display = f"@{username}" if username and not username.isdigit() else str(user_id)
            notif_text = (
                f"**کانفیگ جدید ساخته شد!**\n\n"
                f"**کاربر:** {user_display} (ID: {user_id})\n"
                f"**پلن:** {plan['name']}\n"
                f"**حجم:** {plan['gb']} GB\n"
                f"**مدت:** {plan['days']} روز\n"
                f"**مبلغ:** {plan['price']:,} {symbol}\n\n"
                f"**لینک اشتراک:**\n`{result['sub_link']}`"
            )
            await callback.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data == "buy_config")
async def cb_buy_config(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("لطفاً ابتدا /start را بزنید", show_alert=True)
        return
    from database import get_plan_sections
    sections = await get_plan_sections()
    if sections:
        text = "━━━━━━━━━━━━━━━━━━━━\n  🛒 <b>خرید کانفیگ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n  بخش مورد نظر را انتخاب کنید:"
        reply_markup = await sections_menu()
    else:
        text = await get_setting("plans_header_text") or (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "  🛒 <b>خرید کانفیگ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "  پلن مورد نظر خود را انتخاب کنید:"
        )
        reply_markup = await plans_menu()
    try:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
            except Exception:
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


@router.callback_query(F.data.startswith("select_section_"))
async def cb_select_section(callback: CallbackQuery):
    section_id = int(callback.data.split("_")[-1])
    from database import get_plan_section
    section = await get_plan_section(section_id)
    text = f"━━━━━━━━━━━━━━━━━━━━\n  🛒 <b>{section['name']}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n  پلن مورد نظر را انتخاب کنید:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await plans_menu(section_id))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await plans_menu(section_id))


@router.callback_query(F.data == "all_plans")
async def cb_all_plans(callback: CallbackQuery):
    text = await get_setting("plans_header_text") or (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  🛒 <b>خرید کانفیگ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "  پلن مورد نظر خود را انتخاب کنید:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await plans_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await plans_menu())


@router.callback_query(F.data.startswith("select_plan_"))
async def cb_select_plan(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    volume_line = "" if plan.get("is_ultimate") else f"  📊 حجم: <b>{plan['gb']} GB</b>\n"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  📦 <b>{plan['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{volume_line}"
        f"  📅 مدت: <b>{plan['days']} روز</b>\n"
        f"  💰 قیمت: <b>{plan['price']:,} {symbol}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  روش پرداخت را انتخاب کنید:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))


@router.callback_query(F.data.startswith("pay_wallet_"))
async def cb_pay_wallet(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    symbol = await get_setting("currency_symbol") or "تومان"

    if user["balance"] < plan["price"]:
        text = await no_balance(plan["price"], user["balance"], symbol)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())
        return

    from database import update_balance
    await update_balance(user_id, -plan["price"])

    username = user.get("username") or str(user_id)
    ts = int(time.time())
    email = f"user_{user_id}_{username}_{ts}"

    await callback.answer("در حال ساخت کانفیگ...", show_alert=False)
    plan_inbound_ids = None
    if plan.get("inbound_ids"):
        plan_inbound_ids = [int(x.strip()) for x in plan["inbound_ids"].split(",") if x.strip().isdigit()]
    result = await panel_api.create_config(email, days=plan["days"], total_gb=plan["gb"], inbound_ids=plan_inbound_ids)
    if not result:
        await update_balance(user_id, plan["price"])
        try:
            await callback.message.edit_text(
                "ساخت کانفیگ ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
            )
        except Exception:
            await callback.message.answer(
                "ساخت کانفیگ ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
            )
        return

    await add_config(
        user_id=user_id, plan_id=plan_id, sub_link=result["sub_link"],
        uuid=result["uuid"], email=email, expire_date=result["expire_date"],
    )

    text = await config_created(result["sub_link"], result["expire_date"][:10], plan["price"], plan["name"], plan["gb"], plan["days"], symbol)
    qr_img = generate_qr(result["sub_link"])

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
    )


@router.callback_query(F.data.startswith("pay_c2c_"))
async def cb_pay_c2c(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    symbol = await get_setting("currency_symbol") or "تومان"
    card_number = await get_setting("card_number") or "1234-5678-9012-3456"
    card_owner = await get_setting("card_owner") or "Card Owner"

    await state.update_data(c2c_plan_id=plan_id)
    await state.set_state(C2CState.waiting_confirm)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
    from utils.premium_emoji import pe, get_button_emoji_id
    from keyboards.user import _btn

    copy_card_btn = InlineKeyboardButton(
        text="کپی شماره کارت",
        copy_text=CopyTextButton(text=card_number),
    )
    eid = await get_button_emoji_id("copy_number")
    if eid:
        copy_card_btn.icon_custom_emoji_id = eid

    copy_both_btn = InlineKeyboardButton(
        text="کپی مبلغ",
        copy_text=CopyTextButton(text=f"{plan['price']:,} {symbol}"),
    )
    eid = await get_button_emoji_id("copy_price")
    if eid:
        copy_both_btn.icon_custom_emoji_id = eid

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [copy_card_btn, copy_both_btn],
        [await _btn("پرداخت موفق", f"c2c_confirm_{plan_id}", "success", btn_id="c2c_confirm")],
        [await _btn("لغو", "main_menu", "cancel", "danger", "cancel")],
    ])

    from utils.texts import c2c_payment_text
    text = await c2c_payment_text(plan, symbol, card_number, card_owner)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("c2c_confirm_"))
async def cb_c2c_confirm(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    await state.update_data(c2c_plan_id=plan_id)
    await state.set_state(C2CState.waiting_photo)

    from utils.texts import c2c_upload_photo_text
    text = await c2c_upload_photo_text()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())


@router.message(C2CState.waiting_photo, F.photo)
async def cb_c2c_receipt_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data.get("c2c_plan_id", 0)
    plan = await get_plan(plan_id)

    if not plan:
        await message.answer("پلن یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
        await state.clear()
        return

    photo_file_id = message.photo[-1].file_id
    receipt_id = await add_receipt(message.from_user.id, plan["price"], photo_file_id, plan_id)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    from utils.texts import c2c_receipt_submitted_text
    text = await c2c_receipt_submitted_text(plan, symbol)
    await message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())

    await _send_receipt_to_channel(
        message.bot, photo_file_id,
        f"**New C2C Receipt**\n\n"
        f"User: @{message.from_user.username or 'N/A'} (ID: {message.from_user.id})\n"
        f"Plan: {plan['name']} ({plan['gb']}GB / {plan['days']} days)\n"
        f"Amount: {plan['price']:,} {symbol}\n\n"
        f"Use /admin to review.",
        receipt_id=receipt_id,
    )


@router.callback_query(F.data == "cancel_receipt")
async def cb_cancel_receipt(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Payment cancelled.", reply_markup=await back_to_menu())


@router.callback_query(F.data == "my_configs")
async def cb_my_configs(callback: CallbackQuery):
    user_id = callback.from_user.id
    configs = await get_user_configs(user_id)

    active_configs = [c for c in configs if c["is_active"]]
    text = await service_list_text(active_configs)

    if active_configs:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from keyboards.user import _btn
        buttons = []
        for cfg in active_configs[:5]:
            buttons.append([InlineKeyboardButton(
                text=f"🟢 سرویس #{cfg['id']} — انقضا: {cfg['expire_date'][:10]}",
                callback_data=f"config_detail_{cfg['id']}",
            )])
        btn_back = await get_setting("btn_back")
        buttons.append([await _btn(btn_back, "main_menu", "back", btn_id="back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())


@router.callback_query(F.data.startswith("config_detail_"))
async def cb_config_detail(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    if cfg["user_id"] != callback.from_user.id:
        await callback.answer("این سرویس متعلق به شما نیست!", show_alert=True)
        return

    sub_link = cfg["sub_link"]
    plan_name = await get_plan_name(cfg.get("plan_id"))
    expire_date = cfg["expire_date"][:10]

    traffic_info = None
    try:
        traffic_info = await panel_api.get_client_traffic(cfg["email"])
    except Exception:
        pass

    text = await service_detail_text(config_id, plan_name, expire_date, sub_link, traffic_info)
    qr_img = generate_qr(sub_link)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML",
        reply_markup=await service_detail_keyboard(config_id),
    )


@router.callback_query(F.data.startswith("volume_info_"))
async def cb_volume_info(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    plan_name = await get_plan_name(cfg.get("plan_id"))
    try:
        traffic_info = await panel_api.get_client_traffic(cfg["email"])
    except Exception:
        traffic_info = None

    if not traffic_info:
        await callback.answer("خطا در دریافت اطلاعات حجم!", show_alert=True)
        return

    text = await volume_detail_text(config_id, plan_name, traffic_info)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from keyboards.user import _btn
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("بازگشت", f"config_detail_{config_id}", btn_id="back")],
        ]
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("extract_configs_"))
async def cb_extract_configs(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    try:
        client_configs = await panel_api.get_client_configs(cfg["email"])
    except Exception:
        client_configs = []

    text = await extract_configs_text(config_id, client_configs)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from keyboards.user import _btn
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("بازگشت", f"config_detail_{config_id}", btn_id="back")],
        ]
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("buy_extra_"))
async def cb_buy_extra(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    plan_name = await get_plan_name(cfg.get("plan_id"))
    price_per_gb = int(await get_setting("extra_volume_price_per_gb") or "6000")
    symbol = await get_setting("currency_symbol") or "تومان"

    try:
        traffic_info = await panel_api.get_client_traffic(cfg["email"])
    except Exception:
        traffic_info = None

    current_total_gb = traffic_info["total_gb"] if traffic_info else 0

    text = await buy_extra_volume_text(plan_name, current_total_gb, 0, price_per_gb, symbol)
    kb = await extra_volume_keyboard(config_id, price_per_gb)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("confirm_extra_"))
async def cb_confirm_extra(callback: CallbackQuery):
    parts = callback.data.split("_")
    config_id = int(parts[2])
    extra_gb = int(parts[3])

    cfg = await get_config_by_id(config_id)
    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    price_per_gb = int(await get_setting("extra_volume_price_per_gb") or "6000")
    total_price = extra_gb * price_per_gb
    symbol = await get_setting("currency_symbol") or "تومان"
    user = await get_user(callback.from_user.id)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from keyboards.user import _btn

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰 <b>پرداخت حجم اضافی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  ➕ حجم: <b>{extra_gb} GB</b>\n"
        f"  💰 مبلغ: <b>{total_price:,} {symbol}</b>\n"
        f"  💳 موجودی شما: <b>{user['balance']:,.0f} {symbol}</b>\n\n"
        f"  روش پرداخت را انتخاب کنید:"
    )

    wallet_btn = await _btn(
        f"کیف پول ({user['balance']:,.0f} {symbol})",
        f"pay_extra_wallet_{config_id}_{extra_gb}",
        "card", btn_id="wallet_payment"
    )
    c2c_btn = await _btn(
        "کارت به کارت",
        f"pay_extra_c2c_{config_id}_{extra_gb}",
        "card", btn_id="c2c_payment"
    )
    back_btn = await _btn("بازگشت", f"buy_extra_{config_id}", btn_id="back")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [wallet_btn],
        [c2c_btn],
        [back_btn],
    ])

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("pay_extra_wallet_"))
async def cb_pay_extra_wallet(callback: CallbackQuery):
    parts = callback.data.split("_")
    config_id = int(parts[3])
    extra_gb = int(parts[4])

    cfg = await get_config_by_id(config_id)
    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    price_per_gb = int(await get_setting("extra_volume_price_per_gb") or "6000")
    total_price = extra_gb * price_per_gb
    user_id = callback.from_user.id
    user = await get_user(user_id)
    symbol = await get_setting("currency_symbol") or "تومان"

    if user["balance"] < total_price:
        text = await no_balance_for_extra(total_price, user["balance"], symbol)
        await callback.answer(text, show_alert=True)
        return

    await update_balance(user_id, -total_price)
    await callback.answer("در حال اضافه کردن حجم...", show_alert=False)

    success = await panel_api.update_client_total_gb(cfg["email"], extra_gb)
    if not success:
        await update_balance(user_id, total_price)
        await callback.answer("خطا در اضافه کردن حجم! موجودی بازگردانده شد.", show_alert=True)
        return

    traffic_info = await panel_api.get_client_traffic(cfg["email"])
    new_total_gb = traffic_info["total_gb"] if traffic_info else extra_gb

    text = await extra_volume_success_text(extra_gb, new_total_gb)
    qr_img = generate_qr(cfg["sub_link"])

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML",
        reply_markup=await service_detail_keyboard(config_id),
    )


class ExtraVolumeC2CState(StatesGroup):
    waiting_receipt = State()
    waiting_confirm = State()


@router.callback_query(F.data.startswith("pay_extra_c2c_"))
async def cb_pay_extra_c2c(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    config_id = int(parts[3])
    extra_gb = int(parts[4])

    cfg = await get_config_by_id(config_id)
    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    price_per_gb = int(await get_setting("extra_volume_price_per_gb") or "6000")
    total_price = extra_gb * price_per_gb
    symbol = await get_setting("currency_symbol") or "تومان"
    card_number = await get_setting("card_number") or "1234-5678-9012-3456"
    card_owner = await get_setting("card_owner") or "Card Owner"

    await state.update_data(extra_volume_config_id=config_id, extra_volume_gb=extra_gb, extra_volume_price=total_price)
    await state.set_state(ExtraVolumeC2CState.waiting_confirm)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
    from keyboards.user import _btn

    copy_card_btn = InlineKeyboardButton(
        text="کپی شماره کارت",
        copy_text=CopyTextButton(text=card_number),
    )
    eid = await get_button_emoji_id("copy_number")
    if eid:
        copy_card_btn.icon_custom_emoji_id = eid

    copy_price_btn = InlineKeyboardButton(
        text="کپی مبلغ",
        copy_text=CopyTextButton(text=f"{total_price:,} {symbol}"),
    )
    eid = await get_button_emoji_id("copy_price")
    if eid:
        copy_price_btn.icon_custom_emoji_id = eid

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [copy_card_btn, copy_price_btn],
        [await _btn("پرداخت موفق", f"extra_c2c_confirm_{config_id}_{extra_gb}", "success", btn_id="c2c_confirm")],
        [await _btn("لغو", f"config_detail_{config_id}", btn_id="cancel")],
    ])

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  💳 <b>پرداخت کارت به کارت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  ➕ حجم: <b>{extra_gb} GB</b>\n"
        f"  💰 مبلغ: <b>{total_price:,} {symbol}</b>\n\n"
        f"  شماره کارت: <code>{card_number}</code>\n"
        f"  صاحب کارت: <b>{card_owner}</b>\n\n"
        f"  مبلغ دقیق را به کارت بالا واریز کنید،\n"
        f"  سپس روی <b>پرداخت موفق</b> کلیک کنید\n"
        f"  و رسید خود را آپلود کنید."
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("extra_c2c_confirm_"))
async def cb_extra_c2c_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    config_id = int(parts[4])
    extra_gb = int(parts[5])

    await state.update_data(extra_volume_config_id=config_id, extra_volume_gb=extra_gb)
    await state.set_state(ExtraVolumeC2CState.waiting_receipt)

    from keyboards.user import _btn
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("لغو", f"config_detail_{config_id}", btn_id="cancel")],
    ])

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  📷 <b>آپلود رسید پرداخت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  رسید پرداخت حجم اضافی خود را آپلود کنید.\n"
        f"  پس از بررسی توسط ادمین، حجم اضافه خواهد شد."
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(ExtraVolumeC2CState.waiting_receipt, F.photo)
async def cb_extra_volume_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    config_id = data.get("extra_volume_config_id")
    extra_gb = data.get("extra_volume_gb")
    price = data.get("extra_volume_price")

    photo_file_id = message.photo[-1].file_id
    receipt_id = await add_receipt(message.from_user.id, price, photo_file_id, 0)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  ✅ <b>رسید ارسال شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  ➕ حجم: <b>{extra_gb} GB</b>\n"
        f"  💰 مبلغ: <b>{price:,} {symbol}</b>\n\n"
        f"  ادمین رسید شما را بررسی خواهد کرد.\n"
        f"  پس از تأیید، حجم به سرویس شما اضافه می‌شود."
    )

    await message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())

    await _send_receipt_to_channel(
        message.bot, photo_file_id,
        f"**Extra Volume Receipt**\n\n"
        f"User: @{message.from_user.username or 'N/A'} (ID: {message.from_user.id})\n"
        f"Volume: {extra_gb}GB\n"
        f"Amount: {price:,} {symbol}\n"
        f"Config ID: {config_id}\n\n"
        f"Use /admin to review.",
        receipt_id=receipt_id,
    )


@router.callback_query(F.data.startswith("channel_approve_"))
async def cb_channel_approve(callback: CallbackQuery):
    receipt_id = int(callback.data.split("_")[-1])
    from database import approve_receipt, get_receipt, get_user

    if not await is_admin(callback.from_user.id):
        await callback.answer("فقط ادمین می‌تواند رسید را تایید کند!", show_alert=True)
        return

    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("رسید یافت نشد!", show_alert=True)
        return

    if receipt["status"] != "pending":
        await callback.answer("این رسید قبلاً بررسی شده!", show_alert=True)
        return

    await approve_receipt(receipt_id, callback.from_user.id)
    user = await get_user(receipt["user_id"])
    symbol = await get_setting("currency_symbol") or "تومان"

    try:
        await callback.message.edit_caption(
            caption=(
                f"**Receipt #{receipt_id} - APPROVED**\n\n"
                f"User: ID {receipt['user_id']}\n"
                f"Amount: {receipt['amount']:,.0f} {symbol}\n"
                f"Approved by: @{callback.from_user.username or 'N/A'}"
            ),
        )
    except Exception:
        pass
    await callback.answer("رسید تایید شد!", show_alert=True)

    try:
        if receipt["plan_id"] and receipt["plan_id"] > 0:
            from aiogram.types import InlineKeyboardMarkup
            from keyboards.user import _btn
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [await _btn("ساخت کانفیگ من", f"make_config_{receipt['plan_id']}", "package", btn_id="make_config")],
            ])
            await callback.bot.send_message(
                chat_id=receipt["user_id"],
                text=f"رسید شما تایید شد! ({receipt['amount']:,.0f} {symbol})\n\nروی دکمه زیر کلیک کنید تا کانفیگ شما ساخته شود:",
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


@router.callback_query(F.data.startswith("channel_reject_"))
async def cb_channel_reject(callback: CallbackQuery):
    receipt_id = int(callback.data.split("_")[-1])
    from database import reject_receipt, get_receipt

    if not await is_admin(callback.from_user.id):
        await callback.answer("فقط ادمین می‌تواند رسید را رد کند!", show_alert=True)
        return

    receipt = await get_receipt(receipt_id)
    if not receipt:
        await callback.answer("رسید یافت نشد!", show_alert=True)
        return

    if receipt["status"] != "pending":
        await callback.answer("این رسید قبلاً بررسی شده!", show_alert=True)
        return

    await reject_receipt(receipt_id, callback.from_user.id)
    symbol = await get_setting("currency_symbol") or "تومان"

    try:
        await callback.message.edit_caption(
            caption=(
                f"**Receipt #{receipt_id} - REJECTED**\n\n"
                f"User: ID {receipt['user_id']}\n"
                f"Amount: {receipt['amount']:,.0f} {symbol}\n"
                f"Rejected by: @{callback.from_user.username or 'N/A'}"
            ),
        )
    except Exception:
        pass
    await callback.answer("رسید رد شد!", show_alert=True)


@router.callback_query(F.data.startswith("regen_link_"))
async def cb_regenerate_link(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    text = await regenerate_link_confirm_text()
    kb = await regenerate_link_keyboard(config_id)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("confirm_regen_"))
async def cb_confirm_regenerate(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    await callback.answer("در حال بازسازی لینک...", show_alert=False)
    new_link = await panel_api.regenerate_sub_link(cfg["email"])

    if not new_link:
        await callback.answer("خطا در بازسازی لینک!", show_alert=True)
        return

    await update_config_sub_link(config_id, new_link)
    text = await regenerate_link_success_text(new_link)
    qr_img = generate_qr(new_link)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=qr_img, caption=text, parse_mode="HTML",
        reply_markup=await service_detail_keyboard(config_id),
    )


@router.callback_query(F.data.startswith("copy_link_"))
async def cb_copy_link(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    from database import get_db
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
    db = await get_db()
    cursor = await db.execute("SELECT sub_link FROM configs WHERE id = ?", (config_id,))
    cfg = await cursor.fetchone()
    await db.close()

    if cfg:
        link = cfg["sub_link"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 کپی لینک", copy_text=CopyTextButton(text=link))]
        ])
        await callback.message.answer(f"لینک اشتراک شما:\n<code>{link}</code>", parse_mode="HTML", reply_markup=kb)
        await callback.answer()
    else:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
