from aiogram import Router, F, BaseMiddleware
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
from aiogram.filters import CommandStart, Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from database import (
    add_user, get_user, get_user_configs, has_free_test, add_config,
    get_setting, is_admin, get_plan, add_receipt, get_admins, update_balance,
    get_config_by_id, update_config_sub_link, get_plan_name,
    get_invite_stats, get_active_configs, get_balance,
    add_collab_request, set_user_collaborator,
    is_blacklisted,
    store_support_message, redeem_gift_code, get_guides_by_platform,
    wallet_credit, get_panel,
)
from api import panel_api, panel_manager
from keyboards.user import (
    main_menu, back_to_menu, plans_menu, payment_method_menu, config_detail, name_selection_menu,
    force_join_keyboard, service_detail_keyboard, extra_volume_keyboard,
    regenerate_link_keyboard, sections_menu, view_user_keyboard,
    my_services_panel_menu, my_services_configs_menu, guides_platforms_keyboard,
)
from utils.texts import (
    WELCOME_TEXT_DEFAULT, config_list_text, config_created, free_test_config, no_balance,
    service_list_text, service_detail_text, buy_extra_volume_text, extra_volume_success_text,
    no_balance_for_extra, regenerate_link_confirm_text, regenerate_link_success_text,
    volume_detail_text, extract_configs_text,
)
from utils.premium_emoji import pe, get_button_emoji_id
from utils.stickers import send_sticker
from utils.qr_generator import generate_qr
from io import BytesIO
from data_tracker import log_bot_user, update_user_balance, log_purchase
try:
    from wireguard_api import wireguard_api
except ImportError:
    wireguard_api = None

router = Router()

# TEST_CONFIG_DAYS is now read from settings (free_test_days)


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
    import logging
    _log = logging.getLogger(__name__)
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        return
    try:
        from database import get_user_count_by_period
        from utils.premium_emoji import pe
        today = await get_user_count_by_period(1)
        week = await get_user_count_by_period(7)
        month = await get_user_count_by_period(30)
        lifetime = await get_user_count_by_period(0)
        username = f"@{user.username}" if user.username else "ندارد"
        eu = await pe("users")
        es = await pe("stats")

        tpl = await get_setting("text_new_user_notification") or (
            f"{eu} <b>کاربر جدید ربات را استارت کرد!</b>\n\n"
            f"  👤 نام کاربری: {{username}}\n"
            f"  🔢 آیدی عددی: <code>{{user_id}}</code>\n"
            f"  📛 نام: {{first_name}}\n\n"
            f"  {es} آمار کاربران:\n"
            f"     امروز: <b>{{today}}</b>\n"
            f"     ۷ روز: <b>{{week}}</b>\n"
            f"     ۳۰ روز: <b>{{month}}</b>\n"
            f"     کل: <b>{{lifetime}}</b>"
        )

        text = tpl.replace("{username}", username) \
            .replace("{user_id}", str(user.id)) \
            .replace("{first_name}", user.first_name or "ندارد") \
            .replace("{today}", str(today)) \
            .replace("{week}", str(week)) \
            .replace("{month}", str(month)) \
            .replace("{lifetime}", str(lifetime))

        await bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML", reply_markup=await view_user_keyboard(user.id))
    except Exception as e:
        _log.error("Failed to send new user notification: %s %s", type(e).__name__, e)


async def _send_receipt_to_channel(bot, photo_file_id, caption: str, receipt_id: int = 0):
    import logging
    _log = logging.getLogger(__name__)
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        _log.warning("notification_channel_id not set - skipping channel receipt notification")
        return
    try:
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
        _log.info("Receipt %s sent to channel %s", receipt_id, channel_id)
        if receipt_id:
            try:
                from database import mark_receipt_sent
                await mark_receipt_sent(receipt_id)
            except Exception:
                pass
    except Exception as e:
        _log.error("send_photo to channel %s failed (%s: %s) - trying text fallback", channel_id, type(e).__name__, e)
        try:
            await bot.send_message(chat_id=channel_id, text=caption, parse_mode="Markdown", reply_markup=kb)
            _log.info("Text fallback to channel %s succeeded", channel_id)
        except Exception as e2:
            _log.error("Text fallback also failed for channel %s: %s %s", channel_id, type(e2).__name__, e2)


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


class BlacklistMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        user_id = event.from_user.id
        if await is_blacklisted(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ شما از استفاده از ربات محروم شده‌اید.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("⛔ شما از استفاده از ربات محروم شده‌اید.")
            return
        return await handler(event, data)


router.message.middleware(BlacklistMiddleware())
router.callback_query.middleware(BlacklistMiddleware())


class _StartBtnFilter(BaseFilter):
    async def __call__(self, message) -> bool:
        try:
            btn = await get_setting("btn_start")
            return message.text == (btn or "\u25b6\ufe0f \u0634\u0631\u0648\u0639")
        except Exception:
            return False


_start_btn_match = _StartBtnFilter()

async def _start_kb():
    btn_text = await get_setting("btn_start") or "▶️ شروع"
    btn_style = await get_setting("btn_start_style") or "success"
    emoji_id = await get_setting("btn_start_emoji_id") or ""
    btn = KeyboardButton(text=btn_text, style=btn_style)
    if emoji_id:
        btn.icon_custom_emoji_id = emoji_id
    return ReplyKeyboardMarkup(
        keyboard=[[btn]],
        resize_keyboard=True,
    )

class C2CState(StatesGroup):
    waiting_confirm = State()
    waiting_photo = State()
    upload_photo = State()


class ConfigNameState(StatesGroup):
    waiting_name = State()


class DiscountState(StatesGroup):
    waiting_code = State()


class UserState(StatesGroup):
    support_mode = State()
    waiting_gift_code = State()
    waiting_phone = State()


import json as _json

@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext):
    try:
        data = _json.loads(message.web_app_data.data)
    except Exception:
        return

    action = data.get("action")

    if action == "c2c_upload":
        plan_id = int(data.get("plan_id", 0))
        plan = await get_plan(plan_id)
        if not plan:
            await message.answer("پلن یافت نشد.", reply_markup=await back_to_menu())
            return
        symbol = await get_setting("currency_symbol") or "تومان"
        card_number = await get_setting("card_number") or "1234-5678-9012-3456"
        card_owner = await get_setting("card_owner") or "Card Owner"
        await state.update_data(c2c_plan_id=plan_id)
        from utils.texts import c2c_payment_text
        text = await c2c_payment_text(plan, symbol, card_number, card_owner)
        from keyboards.user import _btn
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [await _btn("پرداخت موفق", f"c2c_confirm_{plan_id}", "success", btn_id="c2c_confirm")],
            [await _btn("لغو", "main_menu", "cancel", "danger", "cancel")],
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if await is_blacklisted(message.from_user.id):
        await message.answer("⛔ شما از استفاده از ربات محروم شده‌اید.")
        return
    args = message.text.split(maxsplit=1)
    param = args[1] if len(args) > 1 else None

    deep_link_actions = {
        "buy_config": "buy_config",
        "wallet": "wallet",
        "free_test": "free_test",
        "my_configs": "my_configs",
        "view_user": "view_user",
    }

    invite_code = None
    deep_link_action = None
    deep_link_param = None
    if param:
        if param in deep_link_actions:
            deep_link_action = deep_link_actions[param]
        elif param.startswith("view_user_"):
            deep_link_action = "view_user"
            deep_link_param = param.replace("view_user_", "")
        elif param.startswith("c2c_"):
            deep_link_action = "c2c"
            deep_link_param = param
        elif param.startswith("upload_receipt_"):
            deep_link_action = "upload_receipt"
            deep_link_param = param
        else:
            invite_code = param

    is_new = await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    log_bot_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")
    if is_new:
        if invite_code:
            from database import get_user_by_invite_code, set_referred_by
            referrer = await get_user_by_invite_code(invite_code)
            if referrer and referrer["id"] != message.from_user.id:
                await set_referred_by(message.from_user.id, referrer["id"])

                invite_enabled = await get_setting("invite_enabled")
                if invite_enabled == "1":
                    reward_type = await get_setting("invite_reward_type") or "fixed"
                    if reward_type == "fixed":
                        reward = float(await get_setting("invite_reward_amount") or "0")
                        if reward > 0:
                            await update_balance(referrer["id"], reward)
                            await send_sticker(message.bot, message.chat.id, 'referral')

                channel_id = await get_setting("notification_channel_id") or ""
                if channel_id:
                    try:
                        stats = await get_invite_stats(referrer["id"])
                        invitee_count = stats["count"]
                        referrer_display = f"@{referrer.get('username')}" if referrer.get("username") else str(referrer["id"])
                        invitee_display = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
                        symbol = await get_setting("currency_symbol") or "تومان"
                        reward_val = float(await get_setting("invite_reward_amount") or "0")
                        invite_enabled_val = await get_setting("invite_enabled")

                        notif_text = (
                            f"👥 <b>زیرمجموعه جدید!</b>\n\n"
                            f"  👤 دعوت‌کننده: {referrer_display} (ID: {referrer['id']})\n"
                            f"  👤 زیرمجموعه: {invitee_display} (ID: {message.from_user.id})\n\n"
                            f"  📊 تعداد زیرمجموعه‌های کاربر: <b>{invitee_count}</b>\n"
                        )
                        reward_type_notif = await get_setting("invite_reward_type") or "fixed"
                        if invite_enabled_val == "1" and reward_val > 0:
                            if reward_type_notif == "fixed":
                                notif_text += f"  💰 پاداش ثابت اعطا شده: <b>{reward_val:,.0f} {symbol}</b>\n"
                            else:
                                notif_text += f"  📊 نوع پاداش: <b>کمیسیون درصدی ( عندالشراء )</b>\n"

                        await message.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="HTML", reply_markup=await view_user_keyboard(referrer["id"]))
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error("Failed invite notification: %s %s", type(e).__name__, e)

        await _notify_new_user(message.bot, message.from_user)

    if deep_link_action:
        from utils.texts import WELCOME_TEXT_DEFAULT
        from database import get_plan_sections, get_user_configs

        if deep_link_action == "buy_config":
            sections = await get_plan_sections()
            if sections:
                text = "━━━━━━━━━━━━━━━━━━━━\n  🛒 <b>خرید سرویس</b>\n━━━━━━━━━━━━━━━━━━━━\n\n  بخش مورد نظر را انتخاب کنید:"
                reply_markup = await sections_menu()
            else:
                text = await get_setting("plans_header_text") or (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "  🛒 <b>خرید سرویس</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "  پلن مورد نظر خود را انتخاب کنید:"
                )
                reply_markup = await plans_menu()
            await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

        elif deep_link_action == "wallet":
            user = await get_user(message.from_user.id)
            symbol = await get_setting("currency_symbol") or "تومان"
            from utils.texts import wallet_text
            text = await wallet_text(user["balance"] if user else 0, symbol, user_id=message.from_user.id)
            await message.answer(text, parse_mode="HTML", reply_markup=await wallet_menu())

        elif deep_link_action == "view_user":
            try:
                target_uid = int(deep_link_param)
            except (ValueError, TypeError):
                target_uid = None

            if target_uid:
                target_user = await get_user(target_uid)
                if target_user:
                    active_configs = await get_active_configs(target_uid)
                    invite_stats = await get_invite_stats(target_uid)
                    balance = await get_balance(target_uid)
                    symbol = await get_setting("currency_symbol") or "تومان"

                    uname = target_user.get("username") or "ندارد"
                    fname = target_user.get("first_name") or "ندارد"
                    joined = (target_user.get("created_at") or "")[:10]

                    text = (
                        "👤 <b>پروفایل کاربر</b>\n\n"
                        f"  🔗 آیدی عددی: <code>{target_uid}</code>\n"
                        f"  👤 نام کاربری: {uname}\n"
                        f"  👥 نام: {fname}\n"
                        f"  📅 تاریخ عضویت: {joined}\n\n"
                        f"  📊 کانفیگ‌های فعال: <b>{len(active_configs)}</b>\n"
                        f"  💰 موجودی: <b>{balance:,.0f} {symbol}</b>\n"
                        f"  👥 زیرمجموعه‌ها: <b>{invite_stats['count']} نفر</b>\n\n"
                        f"کد دعوت: <code>{invite_stats.get('code') or '—'}</code>"
                    )

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="\U0001f4e6 کانفیگ‌های کاربر", callback_data=f"view_user_configs_{target_uid}")],
                    ])

                    try:
                        photos = await message.bot.get_user_profile_photos(target_uid, limit=1)
                        if photos.photos:
                            await message.answer_photo(
                                photo=photos.photos[0][-1].file_id,
                                caption=text,
                                parse_mode="HTML",
                                reply_markup=kb,
                            )
                        else:
                            await message.answer(text, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        await message.answer(text, parse_mode="HTML", reply_markup=kb)
                else:
                    await message.answer("❌ کاربر یافت نشد.", reply_markup=await main_menu())
            else:
                await message.answer("❌ آیدی نامعتبر.", reply_markup=await main_menu())
            return

        elif deep_link_action == "free_test":
            from keyboards.user import _btn
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [await _btn("🧪 تست رایگان", "free_test", "free_test", btn_id="free_test")],
                [await _btn("بازگشت", "main_menu", btn_id="back")],
            ])
            await message.answer(
                "━━━━━━━━━━━━━━━━━━━━\n  🧪 <b>تست رایگان</b>\n━━━━━━━━━━━━━━━━━━━━\n\n  برای دریافت تست رایگان کلیک کنید:",
                parse_mode="HTML", reply_markup=kb,
            )

        elif deep_link_action == "my_configs":
            configs = await get_user_configs(message.from_user.id)
            active = [c for c in configs if c["is_active"]]
            if active:
                buttons = []
                for cfg in active[:5]:
                    svc_name = cfg.get("config_name") or f"سرویس #{cfg['id']}"
                    buttons.append([InlineKeyboardButton(
                        text=f"🟢 {svc_name} — انقضا: {cfg['expire_date'][:10]}",
                        callback_data=f"config_detail_{cfg['id']}",
                    )])
                from keyboards.user import _btn
                buttons.append([await _btn("بازگشت", "main_menu", btn_id="back")])
                kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer("📋 <b>سرویس‌های فعال شما</b>", parse_mode="HTML", reply_markup=kb)
            else:
                await message.answer(
                    "📋 <b>سرویس‌های من</b>\\n\\nشما هیچ سرویس فعالی ندارید.",
                    parse_mode="HTML", reply_markup=await back_to_menu(),
                )

        elif deep_link_action == "c2c":
            try:
                parts = deep_link_param.split("_")
                plan_id = int(parts[1])
            except (IndexError, ValueError):
                plan_id = 0
            plan = await get_plan(plan_id)
            if not plan:
                await message.answer("پلن یافت نشد.", reply_markup=await back_to_menu())
                return
            symbol = await get_setting("currency_symbol") or "تومان"
            card_number = await get_setting("card_number") or "1234-5678-9012-3456"
            card_owner = await get_setting("card_owner") or "Card Owner"
            c2c_cfg_name = ""
            if len(parts) > 2:
                from urllib.parse import unquote
                c2c_cfg_name = unquote("_".join(parts[2:]))
            await state.update_data(c2c_plan_id=plan_id, config_name=c2c_cfg_name)
            await state.set_state(C2CState.waiting_photo)
            from utils.texts import c2c_payment_text, c2c_upload_photo_text
            card_text = await c2c_payment_text(plan, symbol, card_number, card_owner)
            photo_text = await c2c_upload_photo_text()
            text = card_text + "\n\n" + photo_text
            from keyboards.user import _btn
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [await _btn("لغو", "main_menu", "cancel", "danger", "cancel")],
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=kb)

        elif deep_link_action == "upload_receipt":
            try:
                receipt_id = int(deep_link_param.split("_")[2])
            except (IndexError, ValueError):
                receipt_id = 0
            from database import get_receipt
            receipt = await get_receipt(receipt_id) if receipt_id else None
            if not receipt or receipt["user_id"] != message.from_user.id:
                await message.answer("رسید یافت نشد.", reply_markup=await back_to_menu())
                return
            if receipt["status"] != "pending":
                await message.answer("این رسید قبلاً پردازش شده است.", reply_markup=await back_to_menu())
                return
            await state.update_data(upload_receipt_id=receipt_id)
            await state.set_state(C2CState.upload_photo)
            from utils.texts import c2c_upload_photo_text
            text = await c2c_upload_photo_text()
            await message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())

        return

    if not await _is_channel_member(message.bot, message.from_user.id):
        await _send_force_join(message.bot, message.from_user.id)
        return

    phone_enabled = await get_setting("phone_verification_enabled") or "0"
    if phone_enabled == "1":
        user = await get_user(message.from_user.id)
        if user and not user.get("phone"):
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 ارسال شماره تلفن", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await message.answer("لطفاً شماره تلفن خود را ارسال کنید.", reply_markup=kb)
            await state.set_state(UserState.waiting_phone)
            return

    we = await get_setting("welcome_emoji") or ""
    welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
    user = message.from_user
    welcome = welcome.replace("{name}", user.first_name or "دوست عزیز")
    welcome = welcome.replace("{{username}}", f"@{user.username}" if user.username else "")
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    welcome = welcome.replace("{{full_name}}", full_name or "دوست عزیز")
    if we:
        welcome = '<tg-emoji emoji-id="' + we + '">🔹</tg-emoji>\n' + welcome
    await send_sticker(message.bot, message.chat.id, 'welcome')
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


@router.message(_start_btn_match)
async def btn_start(message: Message):
    if await is_blacklisted(message.from_user.id):
        await message.answer("⛔ شما از استفاده از ربات محروم شده‌اید.")
        return
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

    phone_enabled = await get_setting("phone_verification_enabled") or "0"
    if phone_enabled == "1":
        user = await get_user(message.from_user.id)
        if user and not user.get("phone"):
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 ارسال شماره تلفن", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await message.answer("لطفاً شماره تلفن خود را ارسال کنید.", reply_markup=kb)
            return

    we = await get_setting("welcome_emoji") or ""
    if we:
        try: await message.answer(we)
        except: pass
    await send_sticker(message.bot, message.chat.id, 'welcome')
    welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
    user = message.from_user
    welcome = welcome.replace("{name}", user.first_name or "دوست عزیز")
    welcome = welcome.replace("{{username}}", f"@{user.username}" if user.username else "")
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    welcome = welcome.replace("{{full_name}}", full_name or "دوست عزیز")
    menu_msg = await message.answer(welcome, parse_mode="HTML", reply_markup=await main_menu(message.from_user.id))
    try:
        await message.bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[{"type": "emoji", "emoji": "🔥"}],
        )
    except Exception:
        pass


@router.message(UserState.waiting_phone, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("لطفاً شماره خودتان را ارسال کنید.")
        return
    phone = contact.phone_number
    from database import get_db
    db = await get_db()
    await db.execute("UPDATE users SET phone = ?, phone_verified_at = ? WHERE id = ?",
                     (phone, datetime.utcnow().isoformat(), message.from_user.id))
    await db.commit()
    await db.close()
    await state.clear()
    await message.answer("✅ شماره تلفن شما تایید شد.", reply_markup=ReplyKeyboardRemove())

    we = await get_setting("welcome_emoji") or ""
    welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
    user = message.from_user
    welcome = welcome.replace("{name}", user.first_name or "دوست عزیز")
    welcome = welcome.replace("{{username}}", f"@{user.username}" if user.username else "")
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    welcome = welcome.replace("{{full_name}}", full_name or "دوست عزیز")
    if we:
        welcome = '<tg-emoji emoji-id="' + we + '">🔹</tg-emoji>\n' + welcome
    await send_sticker(message.bot, message.chat.id, 'welcome')
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


@router.callback_query(F.data == "check_membership")
async def cb_check_membership(callback: CallbackQuery):
    if await _is_channel_member(callback.bot, callback.from_user.id):
        try:
            await callback.message.delete()
        except Exception:
            pass
        we = await get_setting("welcome_emoji") or ""
        if we:
            try: await callback.message.answer(we)
            except: pass
        welcome = await get_setting("welcome_text") or WELCOME_TEXT_DEFAULT
        user = callback.from_user
        welcome = welcome.replace("{name}", user.first_name or "دوست عزیز")
        welcome = welcome.replace("{{username}}", f"@{user.username}" if user.username else "")
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        welcome = welcome.replace("{{full_name}}", full_name or "دوست عزیز")
        await callback.message.answer(welcome, parse_mode="HTML", reply_markup=await _start_kb())
        menu_msg = await callback.message.answer("منوی اصلی", reply_markup=await main_menu(callback.from_user.id))
        try:
            await callback.bot.set_message_reaction(
                chat_id=callback.message.chat.id,
                message_id=message.message_id,
                reaction=[{"type": "emoji", "emoji": "🔥"}],
            )
        except Exception:
            pass
    else:
        fail_text = await get_setting("force_join_fail_text") or "❌ شما هنوز در کانال عضو نیستید! لطفاً ابتدا عضو شوید و سپس دوباره بررسی کنید."
        await callback.answer(fail_text, show_alert=True)


@router.callback_query(F.data == "invite")
async def cb_invite(callback: CallbackQuery):
    from database import get_setting, get_user_referral_earnings
    enabled = await get_setting("invite_enabled")
    if enabled != "1":
        await callback.answer("این قابلیت غیرفعال است", show_alert=True)
        return
    stats = await get_invite_stats(callback.from_user.id)
    code = stats["code"] or "N/A"
    count = stats["count"]
    reward = await get_setting("invite_reward_amount") or "0"
    reward_type = await get_setting("invite_reward_type") or "fixed"
    commission_pct = await get_setting("invite_commission_percent") or "10"
    symbol = await get_setting("currency_symbol") or "تومان"
    earnings = await get_user_referral_earnings(callback.from_user.id)
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"

    if reward_type == "commission":
        reward_line = f"درصد کمیسیون: <b>{commission_pct}%</b> از خرید زیرمجموعه"
    else:
        reward_line = f"پاداش هر زیرمجموعه: <b>{reward} {symbol}</b>"

    if reward_type == "commission":
        tpl = await get_setting("text_invite_commission") or await get_setting("text_invite") or (
            f"👥 <b>زیرمجموعه گیری</b>\n\n"
            f"لینک دعوت شما:\n<code>{link}</code>\n\n"
            f"تعداد زیرمجموعه‌ها: <b>{count}</b>\n"
            f"درصد کمیسیون: <b>{commission_pct}%</b> از خرید زیرمجموعه\n"
            f"درآمد کل: <b>{earnings:,.0f} {symbol}</b>"
        )
    else:
        tpl = await get_setting("text_invite_fixed") or await get_setting("text_invite") or (
            f"👥 <b>زیرمجموعه گیری</b>\n\n"
            f"لینک دعوت شما:\n<code>{link}</code>\n\n"
            f"تعداد زیرمجموعه‌ها: <b>{count}</b>\n"
            f"پاداش هر زیرمجموعه: <b>{reward} {symbol}</b>\n"
            f"درآمد کل: <b>{earnings:,.0f} {symbol}</b>"
        )
    text = tpl.replace("{link}", link) \
        .replace("{count}", str(count)) \
        .replace("{reward}", str(reward)) \
        .replace("{symbol}", symbol) \
        .replace("{earnings}", f"{earnings:,.0f}") \
        .replace("{commission}", commission_pct)

    from keyboards.user import _btn

    copy_btn = InlineKeyboardButton(
        text=await get_setting("btn_invite_copy") or "📋 کپی لینک دعوت",
        copy_text=CopyTextButton(text=link),
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [copy_btn],
        [await _btn("بازگشت", "main_menu", btn_id="back")],
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


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
    mode = await get_setting("operating_mode") or "NORMAL"
    if mode == "MAINTENANCE":
        msg = await get_setting("maintenance_message") or "ربات در حال بروزرسانی است."
        await callback.answer(msg, show_alert=True)
        return
    if mode == "SALES_PAUSED":
        msg = await get_setting("sales_paused_message") or "فروش موقتاً متوقف شده."
        await callback.answer(msg, show_alert=True)
        return

    user_id = callback.from_user.id
    admin = await is_admin(user_id)
    if not admin and await has_free_test(user_id):
        await callback.answer("You already used your free test!", show_alert=True)
        return

    import database as db
    all_panels = await db.get_active_panels()
    ft_panels = [p for p in all_panels if p.get("free_test_enabled")]
    if not ft_panels:
        await callback.answer("Free test is currently disabled.", show_alert=True)
        return

    from keyboards.user import _btn
    lines = ["🧪 **تست رایگان**\n\nپنل مورد نظر را انتخاب کنید:\n"]
    kb_rows = []
    for p in ft_panels:
        ptype = p.get("panel_type", "v2ray")
        mb = p.get("free_test_mb", 0)
        days = p.get("free_test_days", 1)
        mb_text = f"{mb // 1024}GB" if mb >= 1024 else f"{mb}MB"
        lines.append(f"**{p['name']}** — {mb_text} / {days}روز")
        btn = await _btn(p["name"], f"free_test_select_{p['id']}", "link", btn_id="plan_name")
        if p.get("emoji_id"):
            btn.icon_custom_emoji_id = p["emoji_id"]
        kb_rows.append([btn])
    back = await get_setting("btn_back")
    kb_rows.append([await _btn(back, "main_menu", "back", btn_id="back3")])
    from aiogram.types import InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("free_test_select_"))
async def cb_free_test_select(callback: CallbackQuery):
    panel_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    admin = await is_admin(user_id)
    if not admin and await has_free_test(user_id):
        await callback.answer("You already used your free test!", show_alert=True)
        return

    import database as db
    ft_panel = await db.get_panel(panel_id)
    if not ft_panel or not ft_panel.get("free_test_enabled"):
        await callback.answer("این پنل برای تست رایگان غیرفعال است.", show_alert=True)
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
    free_test_mb = ft_panel.get("free_test_mb") or 102400
    free_test_days = ft_panel.get("free_test_days") or 1
    free_test_inbound_raw = ft_panel.get("free_test_inbound_ids") or ""
    free_test_inbound_ids = [int(x.strip()) for x in free_test_inbound_raw.split(",") if x.strip().isdigit()] or None

    ft_panel_type = ft_panel.get("panel_type", "v2ray")

    if ft_panel_type == "wireguard":
        if not wireguard_api:
            await callback.message.edit_text("پنل Wireguard متصل نیست.", reply_markup=await back_to_menu())
            return
        import random, string
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        peer_name = f"nig_{user_id}_{rand_suffix}"
        ft_data_limit_gb = (free_test_mb / 1024) if free_test_mb else 0
        wg_result = await wireguard_api.create_peer(
            peer_name=peer_name,
            data_limit_gb=ft_data_limit_gb,
            expiry_days=free_test_days,
        )
        if not wg_result:
            await callback.message.edit_text(
                "ساخت کانفیگ ناموفق بود. لطفاً با ادمین تماس بگیرید.", reply_markup=await back_to_menu()
            )
            return
        sub_link = wg_result.get("short_link", "") or f"wireguard:{peer_name}"
        expire_date = (datetime.utcnow() + timedelta(days=free_test_days)).isoformat()
        result = {"sub_link": sub_link, "uuid": peer_name, "expire_date": expire_date}
    elif ft_panel_type == "pasarguard":
        from pasarguard_api import PasarGuardAPI
        pg_api = PasarGuardAPI(
            panel_url=ft_panel["url"],
            panel_user=ft_panel["username"],
            panel_pass=ft_panel["password"],
        )
        login_ok = await pg_api.login()
        if not login_ok:
            await pg_api.close()
            await callback.message.edit_text(
                "ورود به پنل PasarGuard ناموفق بود.", reply_markup=await back_to_menu()
            )
            return
        pg_username = f"free_{user_id}"
        ft_data_limit_gb = (free_test_mb / 1024) if free_test_mb else 0
        pg_result = await pg_api.create_user(
            username=pg_username,
            data_limit_gb=ft_data_limit_gb,
            expire_days=free_test_days,
        )
        if not pg_result:
            await pg_api.close()
            await callback.message.edit_text(
                "ساخت کانفیگ PasarGuard ناموفق بود.", reply_markup=await back_to_menu()
            )
            return
        sub_link = await pg_api.get_subscription_url_for_user(pg_username)
        if not sub_link:
            sub_link = pg_api.build_subscription_url(pg_username)
        expire_date = (datetime.utcnow() + timedelta(days=free_test_days)).isoformat()
        result = {"sub_link": sub_link, "uuid": pg_username, "expire_date": expire_date}
    else:
        ft_panel_api = panel_manager.get(ft_panel["id"]) or panel_api
        result = await ft_panel_api.create_test_config(email, total_mb=free_test_mb, days=free_test_days, custom_inbound_ids=free_test_inbound_ids)
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
        panel_id=ft_panel["id"],
    )
    log_purchase(user_id, username or str(user_id), "Free Test", free_test_mb // 1024, free_test_days, 0, "تومان", "test")

    try:
        await callback.message.delete()
    except Exception:
        pass

    if ft_panel_type == "wireguard":
        from aiogram.types import BufferedInputFile
        conf_content = await wireguard_api.download_config(result["uuid"])
        qr_bytes = await wireguard_api.download_qr(result["uuid"])

        wg_text = (
            "✅ <b>تست رایگان Wireguard ساخته شد!</b>\n\n"
            f"📊 حجم: <b>{free_test_mb // 1024} GB</b>\n"
            f"📅 مدت: <b>{free_test_days} روز</b>\n"
            f"🔗 لینک کوتاه: <code>{result['sub_link']}</code>\n\n"
            "📄 فایل تنظیمات در ادامه ارسال شد."
        )
        await callback.message.answer(wg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(document=conf_file, caption=f"📄 فایل تنظیمات")

        if qr_bytes:
            qr_file = BufferedInputFile(qr_bytes, filename=f"{result['uuid']}_qr.png")
            await callback.message.answer_photo(photo=qr_file, caption=f"📷 QR کد کانفیگ")
    elif ft_panel_type == "pasarguard":
        from aiogram.types import BufferedInputFile
        conf_content = None
        try:
            conf_content = await pg_api.download_wireguard_config(result["sub_link"])
        except Exception as e:
            logger.error(f"PasarGuard free test config download error: {e}")
        finally:
            await pg_api.close()

        pg_text = (
            "✅ <b>تست رایگان PasarGuard ساخته شد!</b>\n\n"
            f"📊 حجم: <b>{free_test_mb // 1024 if free_test_mb >= 1024 else free_test_mb} {'GB' if free_test_mb >= 1024 else 'MB'}</b>\n"
            f"📅 مدت: <b>{free_test_days} روز</b>\n\n"
            f"🔗 لینک اشتراک:\n<code>{result['sub_link']}</code>\n\n"
        )
        if conf_content:
            pg_text += "📄 فایل تنظیمات در ادامه ارسال شد."
        else:
            pg_text += "⚠️ خطا در دانلود فایل تنظیمات. از لینک اشتراک استفاده کنید."
        await callback.message.answer(pg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(document=conf_file, caption=f"📄 فایل تنظیمات")
    else:
        text = await free_test_config(result["sub_link"], free_test_days)
        qr_img = generate_qr(result["sub_link"])
        await send_sticker(callback.bot, callback.message.chat.id, 'success')
        await callback.message.answer_photo(
            photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
        )

    # Notify admin channel
    channel_id = await get_setting("notification_channel_id") or ""
    if channel_id:
        try:
            from utils.premium_emoji import pe
            ef = await pe("free_test")
            ep = await pe("package")
            el = await pe("link")
            user_display = f"@{username}" if username and not username.isdigit() else str(user_id)
            tpl = await get_setting("text_free_test_notification") or (
                f"{ef} <b>کانفیگ رایگان ساخته شد!</b>\n\n"
                f"  👤 کاربر: {{user_display}} (ID: {{user_id}})\n"
                f"  {ep} حجم: <b>{{free_test_mb}} GB</b>\n"
                f"  📅 مدت: <b>{free_test_days} روز</b>\n\n"
                f"  {el} لینک اشتراک:\n"
                f"<code>{{sub_link}}</code>"
            )
            notif_text = tpl.replace("{user_display}", user_display) \
                .replace("{user_id}", str(user_id)) \
                .replace("{free_test_mb}", str(free_test_mb // 1024)) \
                .replace("{sub_link}", result["sub_link"])
            await callback.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="HTML", reply_markup=await view_user_keyboard(user_id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed free test channel notification: %s %s", type(e).__name__, e)


@router.callback_query(F.data.startswith("make_config_"))
async def cb_make_config(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    username = user.get("username") or str(user_id)
    email = f"c2c_{user_id}_{username}_{int(time.time())}"
    mdata = await state.get_data()
    cfg_name = mdata.get("config_name")

    collab_price = plan.get("collaborator_price", 0)
    base_price = plan["price"]
    if user and user.get("is_collaborator") and collab_price > 0:
        base_price = collab_price

    pay_price_mk = mdata.get("discounted_price", base_price)
    disc_code_mk = mdata.get("discount_code", "")
    await state.clear()
    if not cfg_name:
        try:
            import sqlite3
            from config import DB_PATH
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT config_name FROM receipts WHERE user_id = ? AND plan_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user_id, plan_id)).fetchone()
            conn.close()
            if row and row['config_name']:
                cfg_name = row['config_name']
        except Exception:
            pass

    await callback.answer("در حال ساخت کانفیگ...", show_alert=False)
    
    service_type = plan.get("service_type", "v2ray")
    
    # Auto-detect pasarguard from panel type if service_type is v2ray
    if service_type == "v2ray" and plan.get("panel_id"):
        try:
            _plan_panel = await get_panel(plan["panel_id"])
            if _plan_panel and _plan_panel.get("panel_type") == "pasarguard":
                service_type = "pasarguard"
        except Exception:
            pass
    
    if service_type == "wireguard":
        # Wireguard config creation
        if not wireguard_api:
            await callback.message.edit_text("پنل Wireguard متصل نیست. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
            return
        import random, string
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        peer_name = f"nig_{user_id}_{rand_suffix}"
        wg_result = await wireguard_api.create_peer(
            peer_name=peer_name,
            data_limit_gb=plan["gb"],
            expiry_days=plan["days"],
        )
        if not wg_result:
            await callback.message.edit_text("ساخت کانفیگ Wireguard ناموفق بود. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
            return
        sub_link = wg_result.get("short_link", "") or f"wireguard:{peer_name}"
        expire_date = (datetime.utcnow() + timedelta(days=plan["days"])).isoformat()
        result = {"sub_link": sub_link, "uuid": peer_name, "expire_date": expire_date}
    elif service_type == "pasarguard":
        # PasarGuard config creation
        plan_panel_data = None
        if plan.get("panel_id"):
            plan_panel_data = await get_panel(plan["panel_id"])
        if not plan_panel_data:
            await callback.message.edit_text("پنل PasarGuard یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
            return
        from pasarguard_api import PasarGuardAPI
        pg_api = PasarGuardAPI(
            panel_url=plan_panel_data["url"],
            panel_user=plan_panel_data["username"],
            panel_pass=plan_panel_data["password"],
        )
        login_ok = await pg_api.login()
        if not login_ok:
            await pg_api.close()
            await callback.message.edit_text("ورود به پنل PasarGuard ناموفق بود.", reply_markup=await back_to_menu())
            return
        import random, string
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        pg_username = f"nig_{user_id}_{rand_suffix}"
        logger.info(f"PasarGuard: creating user '{pg_username}' for plan '{plan['name']}' ({plan['gb']}GB, {plan['days']}d)")
        pg_result = await pg_api.create_user(
            username=pg_username,
            data_limit_gb=plan["gb"],
            expire_days=plan["days"],
        )
        if not pg_result:
            await pg_api.close()
            await callback.message.edit_text("ساخت کانفیگ PasarGuard ناموفق بود. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
            return
        actual_username = pg_result.get("username", pg_username)
        logger.info(f"PasarGuard: user '{actual_username}' created successfully (id={pg_result.get('id')})")
        # Fetch the user to get the actual subscription URL (with UUID token)
        sub_link = await pg_api.get_subscription_url_for_user(actual_username)
        if not sub_link:
            sub_link = pg_api.build_subscription_url(actual_username)
        logger.info(f"PasarGuard: subscription URL = {sub_link}")
        expire_date = (datetime.utcnow() + timedelta(days=plan["days"])).isoformat()
        result = {"sub_link": sub_link, "uuid": actual_username, "expire_date": expire_date}
        # pg_api stays open for config download below
    else:
        # V2Ray config creation (existing flow)
        plan_inbound_ids = None
        if plan.get("inbound_ids"):
            plan_inbound_ids = [int(x.strip()) for x in plan["inbound_ids"].split(",") if x.strip().isdigit()]
        ip_limit = plan.get("ip_limit", 0) or 0
        plan_panel = panel_manager.get(plan.get("panel_id")) if plan.get("panel_id") else panel_api
        if not plan_panel:
            plan_panel = panel_api
        result = await plan_panel.create_config(email, days=plan["days"], total_gb=plan["gb"], inbound_ids=plan_inbound_ids, ip_limit=ip_limit)
        if not result:
            await callback.message.edit_text("ساخت کانفیگ ناموفق بود. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
            return

    await add_config(
        user_id=user_id, plan_id=plan_id, sub_link=result["sub_link"],
        uuid=result["uuid"], email=email, expire_date=result["expire_date"],
        panel_id=plan.get("panel_id"),
    )

    cashback_pct = float(await get_setting("cashback_percent") or "0")
    if cashback_pct > 0 and pay_price_mk:
        cashback_amount = pay_price_mk * cashback_pct / 100
        unique_key = f"cashback_{user_id}_{int(time.time())}"
        await wallet_credit(user_id, cashback_amount, "CASHBACK", "کش‌بک خرید", unique_key)

    invite_reward_type = await get_setting("invite_reward_type") or "fixed"
    if invite_reward_type == "commission":
        from database import get_user
        buyer_user = await get_user(user_id)
        if buyer_user and buyer_user.get("referred_by"):
            referrer_id = buyer_user["referred_by"]
            commission_pct = float(await get_setting("invite_commission_percent") or "10")
            if commission_pct > 0 and pay_price_mk:
                commission_amount = pay_price_mk * commission_pct / 100
                unique_key_comm = f"commission_{user_id}_{int(time.time())}"
                await wallet_credit(referrer_id, commission_amount, "CASHBACK", f"کمیسیون زیرمجموعه", unique_key_comm)

    await update_balance(user_id, -pay_price_mk)
    symbol = await get_setting("currency_symbol") or "تومان"
    log_purchase(user_id, username, plan["name"], plan["gb"], plan["days"], plan["price"], symbol)

    symbol = await get_setting("currency_symbol") or "تومان"

    try:
        await callback.message.delete()
    except Exception:
        pass

    if service_type == "wireguard":
        from aiogram.types import BufferedInputFile
        conf_content = await wireguard_api.download_config(result["uuid"])
        qr_bytes = await wireguard_api.download_qr(result["uuid"])

        wg_text = (
            "✅ <b>کانفیگ Wireguard ساخته شد!</b>\n\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: <b>{plan['gb']} GB</b>\n"
            f"📅 مدت: <b>{plan['days']} روز</b>\n"
            f"💰 پرداخت: <b>{plan['price']:,} {symbol}</b>\n"
            f"📅 انقضا: <b>{result['expire_date'][:10]}</b>\n\n"
            f"🔗 لینک کوتاه: <code>{result['sub_link']}</code>\n\n"
            "📄 فایل تنظیمات در ادامه ارسال شد."
        )
        await callback.message.answer(wg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(
                document=conf_file,
                caption=f"📄 فایل تنظیمات {result['uuid']}",
            )

        if qr_bytes:
            qr_file = BufferedInputFile(qr_bytes, filename=f"{result['uuid']}_qr.png")
            await callback.message.answer_photo(
                photo=qr_file,
                caption=f"📷 QR کد کانفیگ {result['uuid']}",
            )
    elif service_type == "pasarguard":
        from aiogram.types import BufferedInputFile
        conf_content = None
        logger.info(f"PasarGuard: downloading config from {result['sub_link']}")
        try:
            conf_content = await pg_api.download_wireguard_config(result["sub_link"])
        except Exception as e:
            logger.error(f"PasarGuard config download error: {e}")
        finally:
            await pg_api.close()

        pg_text = (
            "✅ <b>کانفیگ PasarGuard ساخته شد!</b>\n\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: <b>{plan['gb']} GB</b>\n"
            f"📅 مدت: <b>{plan['days']} روز</b>\n"
            f"💰 پرداخت: <b>{plan['price']:,} {symbol}</b>\n"
            f"📅 انقضا: <b>{result['expire_date'][:10]}</b>\n\n"
            f"🔗 لینک اشتراک:\n<code>{result['sub_link']}</code>\n\n"
        )
        if conf_content:
            logger.info(f"PasarGuard: config downloaded successfully ({len(conf_content)} chars)")
            pg_text += "📄 فایل تنظیمات در ادامه ارسال شد."
        else:
            logger.warning("PasarGuard: config download returned None")
            pg_text += "⚠️ خطا در دانلود فایل تنظیمات. از لینک اشتراک استفاده کنید."
        await callback.message.answer(pg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(
                document=conf_file,
                caption=f"📄 فایل تنظیمات {result['uuid']}",
            )
    else:
        # V2Ray: existing flow
        text = await config_created(
            result["sub_link"], result["expire_date"][:10],
            plan["price"], plan["name"], plan["gb"], plan["days"], symbol,
        )
        qr_img = generate_qr(result["sub_link"])
        await send_sticker(callback.bot, callback.message.chat.id, 'config')
        await callback.message.answer_photo(
            photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
        )

    # Notify admin channel
    channel_id = await get_setting("notification_channel_id") or ""
    if channel_id:
        try:
            from utils.premium_emoji import pe
            ep = await pe("package")
            em = await pe("money")
            el = await pe("link")
            eu = await pe("users")
            user_display = f"@{username}" if username and not username.isdigit() else str(user_id)
            tpl = await get_setting("text_new_config_notification") or (
                f"{ep} <b>کانفیگ جدید ساخته شد!</b>\n\n"
                f"  {eu} کاربر: {{user_display}} (ID: {{user_id}})\n"
                f"  📦 پلن: <b>{{plan_name}}</b>\n"
                f"  📊 حجم: <b>{{plan_gb}} GB</b>\n"
                f"  📅 مدت: <b>{{plan_days}} روز</b>\n"
                f"  {em} مبلغ: <b>{{plan_price}} {symbol}</b>\n\n"
                f"  {el} لینک اشتراک:\n"
                f"<code>{{sub_link}}</code>"
            )
            notif_text = tpl.replace("{user_display}", user_display) \
                .replace("{user_id}", str(user_id)) \
                .replace("{plan_name}", plan["name"]) \
                .replace("{plan_gb}", str(plan["gb"])) \
                .replace("{plan_days}", str(plan["days"])) \
                .replace("{plan_price}", f"{plan['price']:,}") \
                .replace("{sub_link}", result["sub_link"])
            await callback.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="HTML", reply_markup=await view_user_keyboard(user_id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed config channel notification: %s %s", type(e).__name__, e)


@router.callback_query(F.data == "buy_config")
async def cb_buy_config(callback: CallbackQuery):
    mode = await get_setting("operating_mode") or "NORMAL"
    if mode == "MAINTENANCE":
        msg = await get_setting("maintenance_message") or "ربات در حال بروزرسانی است."
        await callback.answer(msg, show_alert=True)
        return
    if mode == "SALES_PAUSED":
        msg = await get_setting("sales_paused_message") or "فروش موقتاً متوقف شده."
        await callback.answer(msg, show_alert=True)
        return

    shop_open = await get_setting("shop_open") or "1"
    if shop_open == "0":
        msg = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
        await callback.answer(msg, show_alert=True)
        return
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
    shop_open = await get_setting("shop_open") or "1"
    if shop_open == "0":
        msg = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
        await callback.answer(msg, show_alert=True)
        return
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
    shop_open = await get_setting("shop_open") or "1"
    if shop_open == "0":
        msg = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
        await callback.answer(msg, show_alert=True)
        return
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
async def cb_select_plan(callback: CallbackQuery, state: FSMContext):
    shop_open = await get_setting("shop_open") or "1"
    if shop_open == "0":
        msg = await get_setting("shop_close_message") or "فروش به دلیل بروزرسانی موقتاً بسته شده است."
        await callback.answer(msg, show_alert=True)
        return
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    await state.update_data(config_plan_id=plan_id)

    symbol = await get_setting("currency_symbol") or "تومان"
    volume_line = "" if plan.get("is_ultimate") else f"  📊 حجم: <b>{plan['gb']} GB</b>\n"

    user = await get_user(callback.from_user.id)
    collab_price = plan.get("collaborator_price", 0)
    is_collab = user and user.get("is_collaborator") and collab_price > 0
    display_price = collab_price if is_collab else plan['price']
    collab_line = f"  👥 قیمت همکاری: <b>{collab_price:,} {symbol}</b>\n" if is_collab else ""
    profit = plan['price'] - collab_price if is_collab and collab_price > 0 else 0
    profit_line = f"  💎 سود شما: <b>{profit:,} {symbol}</b>\n" if profit > 0 else ""

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  📦 <b>{plan['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{volume_line}"
        f"  📅 مدت: <b>{plan['days']} روز</b>\n"
        f"  💰 قیمت: <b>{display_price:,} {symbol}</b>\n"
        f"{collab_line}"
        f"{profit_line}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  برای سرویس خود یک نام انتخاب کنید:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await name_selection_menu(plan_id))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await name_selection_menu(plan_id))



@router.callback_query(F.data.startswith("name_custom_"))
async def cb_name_custom(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    await state.update_data(config_plan_id=plan_id)
    await state.set_state(ConfigNameState.waiting_name)
    text = "✏️ <b>نام دلخواه خود را وارد کنید:</b>\n\nحداکثر ۲۰ کاراکتر"
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("name_random_"))
async def cb_name_random(callback: CallbackQuery, state: FSMContext):
    import random
    plan_id = int(callback.data.split("_")[-1])
    words = ["سریع", "آزاد", "امن", "پرسرعت", "نامحدود", "پایدار", "برتر", "ویژه", "فوق‌سریع", "پرواز"]
    name = f"{random.choice(words)}-{random.randint(10, 99)}"
    await state.update_data(config_plan_id=plan_id, config_name=name)
    await show_payment_methods(callback, plan_id)


@router.message(ConfigNameState.waiting_name)
async def handle_config_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()[:20]
    if not name:
        await message.answer("لطفاً یک نام وارد کنید:")
        return
    data = await state.get_data()
    plan_id = data.get("config_plan_id")
    await state.update_data(config_name=name)
    await show_payment_methods(message, plan_id)

async def validate_discount(code_text: str, plan_id: int):
    from database import get_discount_code
    from datetime import datetime
    code = await get_discount_code(code_text.strip().upper())
    if not code:
        return None, "کد تخفیف نامعتبر است."
    if not code["is_active"]:
        return None, "این کد غیرفعال است."
    if code["expires_at"]:
        try:
            exp = datetime.fromisoformat(code["expires_at"])
            if datetime.utcnow() > exp:
                return None, "اعتبار این کد تمام شده است."
        except Exception:
            pass
    if code["max_uses"] > 0 and code["used_count"] >= code["max_uses"]:
        return None, "تعداد استفاده از این کد تمام شده است."
    if code["plan_id"] > 0 and code["plan_id"] != plan_id:
        return None, "این کد برای این پلن معتبر نیست."
    return code, None


def calc_discount(price: float, code: dict) -> tuple[float, str]:
    if code["discount_type"] == "percent":
        amount = price * (code["discount_value"] / 100)
    else:
        amount = min(code["discount_value"], price)
    final = max(0, price - amount)
    return final, f"{amount:,.0f}"


@router.callback_query(F.data.startswith("apply_discount_"))
async def cb_apply_discount(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    await state.update_data(discount_plan_id=plan_id)
    await state.set_state(DiscountState.waiting_code)
    text = "🏷️ <b>کد تخفیف خود را وارد کنید:</b>\n\nپس از اعمال کد، قیمت نهایی نمایش داده می‌شود."
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")


@router.message(DiscountState.waiting_code)
async def handle_discount_code(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("لطفاً کد تخفیف را به صورت متنی وارد کنید:")
        return
    data = await state.get_data()
    plan_id = data.get("discount_plan_id")
    plan = await get_plan(plan_id)
    if not plan:
        await message.answer("پلن یافت نشد.", reply_markup=await back_to_menu())
        await state.clear()
        return

    code, error = await validate_discount(message.text, plan_id)
    if error:
        await message.answer(f"❌ {error}\n\nکد دیگری وارد کنید یا بازگردید:")
        return

    user = await get_user(message.from_user.id)
    collab_price = plan.get("collaborator_price", 0)
    base_for_discount = plan["price"]
    if user and user.get("is_collaborator") and collab_price > 0:
        base_for_discount = collab_price

    final_price, discount_amount_str = calc_discount(base_for_discount, code)
    discount_amount = base_for_discount - final_price
    await state.update_data(
        discount_code=code["code"],
        discount_amount=discount_amount,
        discounted_price=final_price,
    )

    # Send discount usage notification to admin channel
    try:
        channel_id = await get_setting("notification_channel_id") or ""
        if channel_id:
            user_display = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
            type_label = "درصد" if code["discount_type"] == "percent" else "تومان"
            await message.bot.send_message(
                chat_id=channel_id,
                text="🏷️ <b>کد تخفیف اعمال شد!</b>\n\n"
                     f"  👤 کاربر: {user_display} (ID: {message.from_user.id})\n"
                     f"  🏷️ کد: <code>{code['code']}</code>\n"
                     f"  📊 نوع: {type_label} ({code['discount_value']})\n"
                     f"  💰 تخفیف: {discount_amount:,.0f} {symbol}\n"
                     f"  💰 قیمت نهایی: {final_price:,.0f} {symbol}",
                parse_mode="HTML",
            )
    except Exception:
        pass

    saved_cfg = (await state.get_data()).get("config_name", "")
    await state.clear()
    await state.update_data(
        discounted_price=final_price,
        discount_code=code["code"],
        discount_amount=discount_amount,
        config_name=saved_cfg,
    )

    symbol = await get_setting("currency_symbol") or "تومان"
    from keyboards.user import payment_method_menu
    volume_line = "" if plan.get("is_ultimate") else f"  📊 حجم: <b>{plan['gb']} GB</b>\n"
    discount_label = f"{code['discount_value']}{'%' if code['discount_type'] == 'percent' else 'تومان'}"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  📦 <b>{plan['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{volume_line}"
        f"  📅 مدت: <b>{plan['days']} روز</b>\n"
        f"  💰 قیمت: <b>{base_for_discount:,} {symbol}</b>\n"
        f"  🏷️ تخفیف ({discount_label}): <b>\u2212{discount_amount:,.0f} {symbol}</b>\n"
        f"  💰 قیمت نهایی: <b>{final_price:,.0f} {symbol}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  روش پرداخت را انتخاب کنید:"
    )
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))



async def show_payment_methods(target, plan_id: int, discount_amount: float = 0, discount_label: str = ""):
    from database import get_plan, get_setting, get_user
    plan = await get_plan(plan_id)
    symbol = await get_setting("currency_symbol") or "تومان"
    volume_line = "" if plan.get("is_ultimate") else f"  📊 حجم: <b>{plan['gb']} GB</b>\n"

    base_price = plan['price']
    collab_price = plan.get("collaborator_price", 0)

    user_id = None
    if hasattr(target, 'from_user') and target.from_user:
        user_id = target.from_user.id
    elif hasattr(target, 'message') and hasattr(target.message, 'from_user'):
        user_id = target.message.from_user.id

    is_collab = False
    if user_id:
        user = await get_user(user_id)
        if user and user.get("is_collaborator") and collab_price > 0:
            is_collab = True
            base_price = collab_price

    discount_line = ""
    final_price = base_price
    if discount_amount > 0:
        final_price = max(0, base_price - discount_amount)
        discount_line = f"  🏷️ تخفیف ({discount_label}): <b>\u2212{discount_amount:,.0f} {symbol}</b>\n"

    collab_line = ""
    if is_collab and collab_price > 0:
        collab_line = f"  👥 قیمت همکاری: <b>{collab_price:,} {symbol}</b>\n"

    profit = plan['price'] - collab_price if is_collab and collab_price > 0 else 0
    profit_line = f"  💎 سود شما: <b>{profit:,} {symbol}</b>\n" if profit > 0 else ""

    price_display = f"{final_price:,.0f}" if discount_amount > 0 else f"{base_price:,}"
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  📦 <b>{plan['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{volume_line}"
        f"  📅 مدت: <b>{plan['days']} روز</b>\n"
        f"  💰 قیمت: <b>{base_price:,} {symbol}</b>\n"
        f"{collab_line}"
        f"{profit_line}"
        f"{discount_line}"
        f"  💰 قیمت نهایی: <b>{price_display} {symbol}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  روش پرداخت را انتخاب کنید:"
    )
    from aiogram.types import CallbackQuery, Message
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))
        except Exception:
            await target.message.answer(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))
    else:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))
        except Exception:
            await target.answer(text, parse_mode="HTML", reply_markup=await payment_method_menu(plan_id))

@router.callback_query(F.data.startswith("pay_wallet_"))
async def cb_pay_wallet(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    symbol = await get_setting("currency_symbol") or "تومان"

    collab_price = plan.get("collaborator_price", 0)
    base_price = plan["price"]
    if user and user.get("is_collaborator") and collab_price > 0:
        base_price = collab_price

    wdata_pre = await state.get_data()
    pay_price = wdata_pre.get("discounted_price", base_price)
    disc_amount = wdata_pre.get("discount_amount", 0)
    disc_code = wdata_pre.get("discount_code", "")

    if user["balance"] < pay_price:
        text = await no_balance(pay_price, user["balance"], symbol)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())
        return

    from database import update_balance
    await update_balance(user_id, -pay_price)
    update_user_balance(user_id, user["balance"] - pay_price, symbol)

    username = user.get("username") or str(user_id)
    ts = int(time.time())
    email = f"user_{user_id}_{username}_{ts}"
    wdata = await state.get_data()
    cfg_name = wdata.get("config_name")
    await state.clear()

    await callback.answer("در حال ساخت کانفیگ...", show_alert=False)
    
    service_type = plan.get("service_type", "v2ray")
    
    # Auto-detect pasarguard from panel type if service_type is v2ray
    if service_type == "v2ray" and plan.get("panel_id"):
        try:
            _plan_panel = await get_panel(plan["panel_id"])
            if _plan_panel and _plan_panel.get("panel_type") == "pasarguard":
                service_type = "pasarguard"
        except Exception:
            pass
    
    if service_type == "wireguard":
        if not wireguard_api:
            await update_balance(user_id, pay_price)
            await callback.message.edit_text("پنل Wireguard متصل نیست. موجودی بازگردانده شد.", reply_markup=await back_to_menu())
            return
        import random, string
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        peer_name = f"nig_{user_id}_{rand_suffix}"
        wg_result = await wireguard_api.create_peer(
            peer_name=peer_name,
            data_limit_gb=plan["gb"],
            expiry_days=plan["days"],
        )
        if not wg_result:
            await update_balance(user_id, pay_price)
            try:
                await callback.message.edit_text(
                    "ساخت کانفیگ Wireguard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            except Exception:
                await callback.message.answer(
                    "ساخت کانفیگ Wireguard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            return
        sub_link = wg_result.get("short_link", "") or f"wireguard:{peer_name}"
        expire_date = (datetime.utcnow() + timedelta(days=plan["days"])).isoformat()
        result = {"sub_link": sub_link, "uuid": peer_name, "expire_date": expire_date}
    elif service_type == "pasarguard":
        plan_panel_data = None
        if plan.get("panel_id"):
            from database import get_panel
            plan_panel_data = await get_panel(plan["panel_id"])
        if not plan_panel_data:
            await update_balance(user_id, pay_price)
            try:
                await callback.message.edit_text(
                    "پنل PasarGuard یافت نشد. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            except Exception:
                await callback.message.answer(
                    "پنل PasarGuard یافت نشد. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            return
        from pasarguard_api import PasarGuardAPI
        pg_api = PasarGuardAPI(
            panel_url=plan_panel_data["url"],
            panel_user=plan_panel_data["username"],
            panel_pass=plan_panel_data["password"],
        )
        login_ok = await pg_api.login()
        if not login_ok:
            await pg_api.close()
            await update_balance(user_id, pay_price)
            try:
                await callback.message.edit_text(
                    "ورود به پنل PasarGuard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            except Exception:
                await callback.message.answer(
                    "ورود به پنل PasarGuard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            return
        import random, string
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        pg_username = f"nig_{user_id}_{rand_suffix}"
        pg_result = await pg_api.create_user(
            username=pg_username,
            data_limit_gb=plan["gb"],
            expire_days=plan["days"],
        )
        if not pg_result:
            await pg_api.close()
            await update_balance(user_id, pay_price)
            try:
                await callback.message.edit_text(
                    "ساخت کانفیگ PasarGuard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            except Exception:
                await callback.message.answer(
                    "ساخت کانفیگ PasarGuard ناموفق بود. موجودی بازگردانده شد.", reply_markup=await back_to_menu(),
                )
            return
        sub_link = await pg_api.get_subscription_url_for_user(pg_username)
        if not sub_link:
            sub_link = pg_api.build_subscription_url(pg_username)
        expire_date = (datetime.utcnow() + timedelta(days=plan["days"])).isoformat()
        result = {"sub_link": sub_link, "uuid": pg_username, "expire_date": expire_date}
    else:
        plan_inbound_ids = None
        if plan.get("inbound_ids"):
            plan_inbound_ids = [int(x.strip()) for x in plan["inbound_ids"].split(",") if x.strip().isdigit()]
        ip_limit = plan.get("ip_limit", 0) or 0
        plan_panel = panel_manager.get(plan.get("panel_id")) if plan.get("panel_id") else panel_api
        if not plan_panel:
            plan_panel = panel_api
        result = await plan_panel.create_config(email, days=plan["days"], total_gb=plan["gb"], inbound_ids=plan_inbound_ids, ip_limit=ip_limit)
        if not result:
            await update_balance(user_id, pay_price)
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
        panel_id=plan.get("panel_id"), config_name=cfg_name,
    )

    cashback_pct = float(await get_setting("cashback_percent") or "0")
    if cashback_pct > 0 and pay_price:
        cashback_amount = pay_price * cashback_pct / 100
        unique_key = f"cashback_{user_id}_{int(time.time())}"
        await wallet_credit(user_id, cashback_amount, "CASHBACK", "کش‌بک خرید", unique_key)

    if disc_code:
        try:
            from database import get_discount_code, use_discount_code as _use_dc
            dc = await get_discount_code(disc_code)
            if dc:
                await _use_dc(dc["id"])
        except Exception:
            pass

    try:
        await callback.message.delete()
    except Exception:
        pass

    if service_type == "wireguard":
        from aiogram.types import BufferedInputFile
        conf_content = await wireguard_api.download_config(result["uuid"])
        qr_bytes = await wireguard_api.download_qr(result["uuid"])

        wg_text = (
            "✅ <b>کانفیگ Wireguard ساخته شد!</b>\n\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: <b>{plan['gb']} GB</b>\n"
            f"📅 مدت: <b>{plan['days']} روز</b>\n"
            f"💰 پرداخت: <b>{pay_price:,} {symbol}</b>\n"
            f"📅 انقضا: <b>{result['expire_date'][:10]}</b>\n\n"
            f"🔗 لینک کوتاه: <code>{result['sub_link']}</code>\n\n"
            "📄 فایل تنظیمات در ادامه ارسال شد."
        )
        await callback.message.answer(wg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(
                document=conf_file,
                caption=f"📄 فایل تنظیمات {result['uuid']}",
            )

        if qr_bytes:
            qr_file = BufferedInputFile(qr_bytes, filename=f"{result['uuid']}_qr.png")
            await callback.message.answer_photo(
                photo=qr_file,
                caption=f"📷 QR کد کانفیگ {result['uuid']}",
            )
    elif service_type == "pasarguard":
        from aiogram.types import BufferedInputFile
        conf_content = None
        logger.info(f"PasarGuard (C2C): downloading config from {result['sub_link']}")
        try:
            conf_content = await pg_api.download_wireguard_config(result["sub_link"])
        except Exception as e:
            logger.error(f"PasarGuard config download error: {e}")
        finally:
            await pg_api.close()

        pg_text = (
            "✅ <b>کانفیگ PasarGuard ساخته شد!</b>\n\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: <b>{plan['gb']} GB</b>\n"
            f"📅 مدت: <b>{plan['days']} روز</b>\n"
            f"💰 پرداخت: <b>{pay_price:,} {symbol}</b>\n"
            f"📅 انقضا: <b>{result['expire_date'][:10]}</b>\n\n"
            f"🔗 لینک اشتراک:\n<code>{result['sub_link']}</code>\n\n"
        )
        if conf_content:
            logger.info(f"PasarGuard (C2C): config downloaded successfully ({len(conf_content)} chars)")
            pg_text += "📄 فایل تنظیمات در ادامه ارسال شد."
        else:
            logger.warning("PasarGuard (C2C): config download returned None")
            pg_text += "⚠️ خطا در دانلود فایل تنظیمات. از لینک اشتراک استفاده کنید."
        await callback.message.answer(pg_text, parse_mode="HTML", reply_markup=await back_to_menu())

        if conf_content:
            conf_file = BufferedInputFile(conf_content.encode("utf-8"), filename=f"{result['uuid']}.conf")
            await callback.message.answer_document(
                document=conf_file,
                caption=f"📄 فایل تنظیمات {result['uuid']}",
            )
    else:
        text = await config_created(result["sub_link"], result["expire_date"][:10], pay_price, plan["name"], plan["gb"], plan["days"], symbol)
        qr_img = generate_qr(result["sub_link"])
        await callback.message.answer_photo(
            photo=qr_img, caption=text, parse_mode="HTML", reply_markup=await back_to_menu(),
        )

    # Notify admin channel - wallet payment
    channel_id = await get_setting("notification_channel_id") or ""
    if channel_id:
        try:
            from utils.premium_emoji import pe
            ep = await pe("package")
            em = await pe("money")
            el = await pe("link")
            eu = await pe("users")
            user_display = f"@{username}" if username and not username.isdigit() else str(user_id)
            tpl = await get_setting("text_new_config_notification") or (
                f"{ep} <b>کانفیگ جدید ساخته شد!</b>\n\n"
                f"  {eu} کاربر: {{user_display}} (ID: {{user_id}})\n"
                f"  📦 پلن: <b>{{plan_name}}</b>\n"
                f"  📊 حجم: <b>{{plan_gb}} GB</b>\n"
                f"  📅 مدت: <b>{{plan_days}} روز</b>\n"
                f"  {em} مبلغ: <b>{{plan_price}} {symbol}</b>\n"
                f"  💳 پرداخت: <b>کیف پول</b>\n\n"
                f"  {el} لینک اشتراک:\n"
                f"<code>{{sub_link}}</code>"
            )
            notif_text = tpl.replace("{user_display}", user_display) \
                .replace("{user_id}", str(user_id)) \
                .replace("{plan_name}", plan["name"]) \
                .replace("{plan_gb}", str(plan["gb"])) \
                .replace("{plan_days}", str(plan["days"])) \
                .replace("{plan_price}", f"{plan['price']:,}") \
                .replace("{sub_link}", result["sub_link"])
            await callback.bot.send_message(chat_id=channel_id, text=notif_text, parse_mode="HTML", reply_markup=await view_user_keyboard(user_id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed wallet config notification: %s %s", type(e).__name__, e)


@router.callback_query(F.data.startswith("pay_c2c_"))
async def cb_pay_c2c(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split("_")[-1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("پلن یافت نشد!", show_alert=True)
        return

    user = await get_user(callback.from_user.id)
    symbol = await get_setting("currency_symbol") or "تومان"
    card_number = await get_setting("card_number") or "1234-5678-9012-3456"
    card_owner = await get_setting("card_owner") or "Card Owner"

    collab_price = plan.get("collaborator_price", 0)
    base_price = plan["price"]
    if user and user.get("is_collaborator") and collab_price > 0:
        base_price = collab_price

    c2c_data = await state.get_data()
    c2c_pay_price = c2c_data.get("discounted_price", base_price)
    await state.update_data(c2c_plan_id=plan_id, c2c_pay_price=c2c_pay_price)
    await state.set_state(C2CState.waiting_confirm)

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
        copy_text=CopyTextButton(text=f"{c2c_pay_price:,.0f} {symbol}"),
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
    text = await c2c_payment_text(plan, symbol, card_number, card_owner, pay_price=c2c_pay_price)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("c2c_confirm_"))
async def cb_c2c_confirm(callback: CallbackQuery, state: FSMContext):
    import logging; logging.getLogger("receipt_debug").info("c2c_confirm fired for plan %s, user %s", callback.data, callback.from_user.id)
    plan_id = int(callback.data.split("_")[-1])
    await state.update_data(c2c_plan_id=plan_id)
    await state.set_state(C2CState.waiting_photo)

    from utils.texts import c2c_upload_photo_text
    text = await c2c_upload_photo_text()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())


@router.message(C2CState.waiting_photo, F.photo)
async def cb_c2c_receipt_photo(message: Message, state: FSMContext):
    import logging
    _log = logging.getLogger("receipt_debug")
    _log.info("C2C receipt photo received from user %s, state=%s", message.from_user.id, await state.get_state())
    data = await state.get_data()
    plan_id = data.get("c2c_plan_id", 0)
    plan = await get_plan(plan_id)

    if not plan:
        await message.answer("پلن یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=await back_to_menu())
        await state.clear()
        return

    photo_file_id = message.photo[-1].file_id
    cfg_name = data.get("config_name", "")
    receipt_id = await add_receipt(message.from_user.id, data.get("c2c_pay_price", plan["price"]), photo_file_id, plan_id, config_name=cfg_name)
    await state.clear()

    symbol = await get_setting("currency_symbol") or "تومان"
    from utils.texts import c2c_receipt_submitted_text
    text = await c2c_receipt_submitted_text(plan, symbol, pay_price=data.get("c2c_pay_price", plan["price"]))
    await message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())

    await _send_receipt_to_channel(
        message.bot, photo_file_id,
        f"**New C2C Receipt**\n\n"
        f"User: @{message.from_user.username or 'N/A'} (ID: {message.from_user.id})\n"
        f"Plan: {plan['name']} ({plan['gb']}GB / {plan['days']} days)\n"
        f"Amount: {{data.get('c2c_pay_price', plan['price']):,.0f}} {symbol}\n\n"
        f"Use /admin to review.",
        receipt_id=receipt_id,
    )


@router.message(C2CState.upload_photo, F.photo)
async def cb_upload_receipt_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("upload_receipt_id", 0)

    from database import get_receipt, get_plan
    receipt = await get_receipt(receipt_id)
    if not receipt or receipt["user_id"] != message.from_user.id:
        await message.answer("رسید یافت نشد.", reply_markup=await back_to_menu())
        await state.clear()
        return

    if receipt["status"] != "pending":
        await message.answer("این رسید قبلاً پردازش شده است.", reply_markup=await back_to_menu())
        await state.clear()
        return

    photo_file_id = message.photo[-1].file_id

    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("UPDATE receipts SET photo_file_id = ? WHERE id = ?", (photo_file_id, receipt_id))
    conn.commit()
    conn.close()

    await state.clear()

    plan = await get_plan(receipt["plan_id"]) if receipt["plan_id"] else None
    symbol = await get_setting("currency_symbol") or "تومان"

    if plan:
        from utils.texts import c2c_receipt_submitted_text
        text = await c2c_receipt_submitted_text(plan, symbol)
    else:
        text = "✅ <b>رسید شما دریافت شد</b>\n\nپس از بررسی توسط ادمین، نتیجه اطلاع رسانی خواهد شد."

    await message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())

    caption_parts = ["**رسید جدید**\n\n"]
    caption_parts.append(f"User: @{message.from_user.username or 'N/A'} (ID: {message.from_user.id})\n")
    if plan:
        caption_parts.append(f"Plan: {plan['name']} ({plan['gb']}GB / {plan['days']} days)\n")
        caption_parts.append(f"Amount: {plan['price']:,} {symbol}\n")
    else:
        caption_parts.append(f"Amount: {receipt['amount']:,} {symbol} (Wallet Top-up)\n")
    caption_parts.append("\nUse /admin to review.")
    caption = "".join(caption_parts)

    await _send_receipt_to_channel(
        message.bot, photo_file_id, caption, receipt_id=receipt_id,
    )


@router.callback_query(F.data == "cancel_receipt")
async def cb_cancel_receipt(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Payment cancelled.", reply_markup=await back_to_menu())


@router.callback_query(F.data == "my_configs")
async def cb_my_configs(callback: CallbackQuery):
    user_id = callback.from_user.id
    configs = await get_user_configs(user_id)
    active_configs = [c for c in configs if c.get("is_active")]
    from utils.premium_emoji import pe
    el = await pe("list")
    text = f"━━━━━━━━━━━━━━━━━━━━\n  {el} <b>سرویس‌های من</b>\n━━━━━━━━━━━━━━━━━━━━"

    if active_configs:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await my_services_panel_menu(user_id))
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=await my_services_panel_menu(user_id))
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=await back_to_menu())


@router.callback_query(F.data.startswith("my_services_panel_"))
async def cb_my_services_panel(callback: CallbackQuery):
    user_id = callback.from_user.id
    panel_id = int(callback.data.split("_")[-1])
    from database import get_panel
    panel = await get_panel(panel_id)
    panel_name = panel["name"] if panel else "پنل"
    text = f"📦 <b>{panel_name}</b>\n\nسرویس خود را انتخاب کنید:"
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await my_services_configs_menu(user_id, panel_id))
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await my_services_configs_menu(user_id, panel_id))

class CollabRequestState(StatesGroup):
    waiting_text = State()


# --- Collaboration Request Flow ---
@router.callback_query(F.data == "collab_request")
async def cb_collab_request(callback: CallbackQuery, state: FSMContext):
    enabled = await get_setting("collab_enabled")
    if enabled != "1":
        await callback.answer("این قابلیت غیرفعال است", show_alert=True)
        return
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("لطفاً ابتدا /start را بزنید", show_alert=True)
        return
    if user.get("is_collaborator"):
        await callback.answer("✅ همکاری شما تایید شده است! شما از قیمت‌های ویژه بهره‌مند هستید.", show_alert=True)
        return
    await state.set_state(CollabRequestState.waiting_text)
    text = (
        "🤝 <b>درخواست همکاری</b>\n"
        "\nلطفاً درباره کار خود تضخیر دهید:\n"
        "(نحوه همکاری، تعداد مشتریان و...)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.message(CollabRequestState.waiting_text)
async def process_collab_request(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("لطفاً توضیحات بیشتری بنویسید (حداقل 5 کاراکتر):")
        return

    user_id = message.from_user.id
    username = message.from_user.username or "ندارد"
    first_name = message.from_user.first_name or ""
    request_text = message.text.strip()

    request_id = await add_collab_request(user_id, request_text)

    await state.clear()

    channel_id = await get_setting("collab_notification_channel") or await get_setting("notification_channel_id")
    if channel_id:
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ تایید", callback_data=f"collab_approve_{request_id}"),
                    InlineKeyboardButton(text="❌ رد", callback_data=f"collab_reject_{request_id}"),
                ]
            ])
            admin_text = (
                f"🤝 <b>درخواست همکاری جدید</b>\n"
                f"👤 کاربر: @{username} (ID: <code>{user_id}</code>)\n"
                f"📝 نام: {first_name}\n"
                f"💬 پیام:\n{request_text}"
            )
            await message.bot.send_message(chat_id=channel_id, text=admin_text, parse_mode="HTML", reply_markup=admin_kb)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed collab notification: %s", e)

    await message.answer(
        "✅ درخواست شما ارسال شد!\nپس از بررسی توسط مدیر به شما اطلاع داده خواهد شد.",
        reply_markup=await back_to_menu()
    )


# --- Recover config flow ---
class RecoverState(StatesGroup):
    waiting_link = State()
    waiting_name = State()




@router.callback_query(F.data.startswith("recover_config_"))
async def cb_recover_config(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != (await get_user(callback.from_user.id) or {}).get("id") and not await get_user(callback.from_user.id):
        await callback.answer("لطفاً ابتدا /start را بزنید", show_alert=True)
        return
    panel_id = int(callback.data.split("_")[-1])
    await state.update_data(recover_panel_id=panel_id)
    await state.set_state(RecoverState.waiting_link)
    text = (
        "🔗 <b>بازیابی کانفیگ</b>\n\n"
        "لینک اشتراک (sub link) خود را ارسال کنید:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"my_services_panel_{panel_id}")]
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.message(RecoverState.waiting_link)
async def process_recover_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    panel_id = data["recover_panel_id"]
    link = message.text.strip()

    if not link.startswith("http"):
        await message.answer("لینک معتبر نیست. لطفاً دوباره تلاش کنید:")
        return

    # Check if link already exists in user's configs
    existing = await get_user_configs(user_id)
    for cfg in existing:
        if cfg.get("sub_link") == link:
            await message.answer(
                "⚠️ این لینک قبلاً در سرویس‌های شما موجود است.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"my_services_panel_{panel_id}")]
                ])
            )
            await state.clear()
            return

    await state.update_data(recover_link=link)
    await state.set_state(RecoverState.waiting_name)
    text = "📝 <b>نام سرویس</b>\n\nیک نام برای این سرویس وارد کنید:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data=f"my_services_panel_{panel_id}")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(RecoverState.waiting_name)
async def process_recover_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    panel_id = data["recover_panel_id"]
    link = data["recover_link"]
    config_name = message.text.strip()

    # Extract sub_id from link for expire_date and uuid
    import re
    sub_match = re.search(r'/sub/([a-f0-9-]+)', link)
    sub_id = sub_match.group(1) if sub_match else None

    from database import get_plan
    plan = await get_plan((await get_user_configs(user_id) or [{}])[0].get("plan_id")) if await get_user_configs(user_id) else None
    days = 30
    if plan:
        days = plan.get("days", 30)

    from datetime import datetime, timedelta
    from utils.texts import to_jalali
    expire_date = (datetime.now() + timedelta(days=days)).isoformat()

    await add_config(
        user_id=user_id,
        plan_id=0,
        sub_link=link,
        uuid=sub_id or "",
        email=f"recover_{user_id}",
        expire_date=expire_date,
        panel_id=panel_id,
        config_name=config_name,
    )

    await state.clear()
    text = (
        f"✅ <b>سرویس اضافه شد!</b>\n\n"
        f"📦 نام: {config_name}\n"
        f"📅 تاریخ انقضا: {to_jalali(expire_date)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"my_services_panel_{panel_id}")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


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
        _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
        if not _cpanel: _cpanel = panel_api
        traffic_info = await _cpanel.get_client_traffic(cfg["email"])
    except Exception:
        pass

    text = await service_detail_text(config_id, plan_name, expire_date, sub_link, traffic_info, config_name=cfg.get("config_name") or "")
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
        _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
        if not _cpanel: _cpanel = panel_api
        traffic_info = await _cpanel.get_client_traffic(cfg["email"])
    except Exception:
        traffic_info = None

    if not traffic_info:
        await callback.answer("خطا در دریافت اطلاعات حجم!", show_alert=True)
        return

    text = await volume_detail_text(config_id, plan_name, traffic_info)

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
        _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
        if not _cpanel: _cpanel = panel_api
        client_configs = await _cpanel.get_client_configs(cfg["email"])
    except Exception:
        client_configs = []

    text = await extract_configs_text(config_id, client_configs)

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
        _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
        if not _cpanel: _cpanel = panel_api
        traffic_info = await _cpanel.get_client_traffic(cfg["email"])
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

    _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
    if not _cpanel: _cpanel = panel_api
    success = await _cpanel.update_client_total_gb(cfg["email"], extra_gb)
    if not success:
        await update_balance(user_id, total_price)
        await callback.answer("خطا در اضافه کردن حجم! موجودی بازگردانده شد.", show_alert=True)
        return

    _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
    if not _cpanel: _cpanel = panel_api
    traffic_info = await _cpanel.get_client_traffic(cfg["email"])
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
    from keyboards.user import is_admin

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
    from keyboards.user import is_admin

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
    _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
    if not _cpanel: _cpanel = panel_api
    new_link = await _cpanel.regenerate_sub_link(cfg["email"])

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




@router.callback_query(F.data.startswith("qr_"))
async def cb_show_qr(callback: CallbackQuery):
    config_id = int(callback.data.split("_")[-1])
    cfg = await get_config_by_id(config_id)

    if not cfg or cfg["user_id"] != callback.from_user.id:
        await callback.answer("سرویس یافت نشد!", show_alert=True)
        return

    sub_link = cfg["sub_link"]
    qr_img = generate_qr(sub_link)
    await callback.answer()
    await callback.message.answer_photo(
        photo=qr_img, caption="📱 <b>QR کد لینک اشتراک</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("view_user_configs_"))
async def cb_view_user_configs(callback: CallbackQuery):
    try:
        uid = int(callback.data.split("_")[-1])
    except ValueError:
        return

    configs = await get_user_configs(uid)
    if not configs:
        await callback.answer("این کاربر هیچ کانفیگی ندارد!", show_alert=True)
        return

    await callback.answer("در حال بارگذاری...", show_alert=False)

    for cfg in configs[:10]:
        sub_link = cfg.get("sub_link") or ""
        plan_name = await get_plan_name(cfg.get("plan_id"))
        expire_date = (cfg.get("expire_date") or "")[:10]
        svc_name = cfg.get("config_name") or f"سرویس #{cfg['id']}"

        traffic_info = None
        try:
            _cpanel = panel_manager.get(cfg.get("panel_id")) if cfg.get("panel_id") else panel_api
            if not _cpanel: _cpanel = panel_api
            traffic_info = await _cpanel.get_client_traffic(cfg["email"])
        except Exception:
            pass

        status = "🟢" if cfg.get("is_active") else "🔴"
        detail = f"{status} <b>{svc_name}</b> — {plan_name}\n  انقضا: {expire_date}\n"

        if traffic_info:
            detail += f"  📊 {traffic_info['used_gb']}/{traffic_info['total_gb']} GB\n"
        else:
            plan = await get_plan(cfg.get("plan_id"))
            if plan:
                detail += f"  📊 {plan.get('gb', '?')} GB\n"

        if sub_link:
            detail += f"  🔗 <code>{sub_link}</code>"

        qr_img = generate_qr(sub_link)
        try:
            await callback.message.answer_photo(
                photo=qr_img,
                caption=detail,
                parse_mode="HTML",
            )
        except Exception:
            try:
                await callback.message.answer(detail, parse_mode="HTML")
            except Exception:
                pass

    try:
        await callback.message.answer("پایان لیست کانفیگ‌ها.", parse_mode="HTML")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# SECTION: Support Message Forwarding
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.support_mode)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(
            "💬 <b>پشتیبانی</b>\n\nپیام خود را برای پشتیبانی ارسال کنید:\nبرای لغو /cancel تایپ کنید.",
            parse_mode="HTML", reply_markup=kb,
        )
    except Exception:
        await callback.message.answer(
            "💬 <b>پشتیبانی</b>\n\nپیام خود را برای پشتیبانی ارسال کنید:\nبرای لغو /cancel تایپ کنید.",
            parse_mode="HTML", reply_markup=kb,
        )
    await callback.answer()


@router.message(UserState.support_mode)
async def handle_support_message(message: Message, state: FSMContext):
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        await message.answer("❌ پشتیبانی در دسترس نیست.", reply_markup=await back_to_menu())
        await state.clear()
        return

    user_id = message.from_user.id
    username = message.from_user.username or "ندارد"
    first_name = message.from_user.first_name or ""

    header = f"📩 <b>پیام جدید از کاربر</b>\n\n👤 کاربر: <code>{user_id}</code> (@{username})\n📛 نام: {first_name}\n\n━━━━━━━━━━━━━━━━━━━━━━"

    try:
        if message.text:
            sent = await message.bot.send_message(
                chat_id=channel_id,
                text=f"{header}\n\n💬 {message.text}",
                parse_mode="HTML",
            )
        elif message.photo:
            sent = await message.bot.send_photo(
                chat_id=channel_id,
                photo=message.photo[-1].file_id,
                caption=f"{header}\n\n📷 {message.caption or ''}",
                parse_mode="HTML",
            )
        elif message.document:
            sent = await message.bot.send_document(
                chat_id=channel_id,
                document=message.document.file_id,
                caption=f"{header}\n\n📄 {message.caption or ''}",
                parse_mode="HTML",
            )
        elif message.voice:
            sent = await message.bot.send_voice(
                chat_id=channel_id,
                voice=message.voice.file_id,
                caption=f"{header}",
                parse_mode="HTML",
            )
        elif message.video:
            sent = await message.bot.send_video(
                chat_id=channel_id,
                video=message.video.file_id,
                caption=f"{header}\n\n🎬 {message.caption or ''}",
                parse_mode="HTML",
            )
        else:
            sent = await message.bot.send_message(
                chat_id=channel_id,
                text=f"{header}\n\n📎 [Unsupported message type]",
                parse_mode="HTML",
            )

        await store_support_message(sent.message_id, user_id)
        await message.answer(
            "✅ پیام شما ارسال شد. پاسخ ادمین را منتظر باشید.",
            reply_markup=await back_to_menu(),
        )
        await state.clear()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to forward support message: %s %s", type(e).__name__, e)
        await message.answer(
            "❌ خطا در ارسال پیام. لطفاً دوباره تلاش کنید.",
            reply_markup=await back_to_menu(),
        )
        await state.clear()


@router.message(Command("cancel"), UserState.support_mode)
async def cmd_cancel_support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ پشتیبانی لغو شد.", reply_markup=await main_menu(message.from_user.id))


# ═══════════════════════════════════════════════════════════════
# SECTION: Gift Code Redemption
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "redeem_gift")
async def cb_redeem_gift(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_gift_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(
            "🎁 <b>کد هدیه</b>\n\nکد هدیه خود را وارد کنید:",
            parse_mode="HTML", reply_markup=kb,
        )
    except Exception:
        await callback.message.answer(
            "🎁 <b>کد هدیه</b>\n\nکد هدیه خود را وارد کنید:",
            parse_mode="HTML", reply_markup=kb,
        )
    await callback.answer()


@router.message(UserState.waiting_gift_code)
async def handle_gift_code(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("لطفاً کد هدیه را به صورت متنی وارد کنید:")
        return

    code = message.text.strip().upper()
    user_id = message.from_user.id
    symbol = await get_setting("currency_symbol") or "تومان"

    amount = await redeem_gift_code(code, user_id)
    await state.clear()

    if amount > 0:
        await update_balance(user_id, amount)
        user = await get_user(user_id)
        new_balance = user["balance"] if user else 0
        await message.answer(
            f"✅ <b>کد هدیه با موفقیت اعمال شد!</b>\n\n"
            f"💰 مبلغ: <b>{amount:,.0f} {symbol}</b>\n"
            f"💰 موجودی جدید: <b>{new_balance:,.0f} {symbol}</b>",
            parse_mode="HTML", reply_markup=await back_to_menu(),
        )
    else:
        await message.answer(
            "❌ کد هدیه نامعتبر است، منقضی شده یا قبلاً استفاده شده است.",
            reply_markup=await back_to_menu(),
        )


# ═══════════════════════════════════════════════════════════════
# SECTION: Connection Guides
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "guides")
async def cb_guides(callback: CallbackQuery):
    from keyboards.user import guides_platforms_keyboard
    try:
        await callback.message.edit_text(
            "📖 <b>راهنمای اتصال</b>\n\nپلتفرم مورد نظر را انتخاب کنید:",
            parse_mode="HTML", reply_markup=await guides_platforms_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            "📖 <b>راهنمای اتصال</b>\n\nپلتفرم مورد نظر را انتخاب کنید:",
            parse_mode="HTML", reply_markup=await guides_platforms_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("guide_platform_"))
async def cb_guide_platform(callback: CallbackQuery):
    platform = callback.data.replace("guide_platform_", "")
    guides = await get_guides_by_platform(platform)

    if not guides:
        try:
            await callback.message.edit_text(
                f"📖 <b>راهنمای {platform}</b>\n\nهنوز راهنمایی برای این پلتفرم اضافه نشده است.",
                parse_mode="HTML", reply_markup=await back_to_menu(),
            )
        except Exception:
            await callback.message.answer(
                f"📖 <b>راهنمای {platform}</b>\n\nهنوز راهنمایی برای این پلتفرم اضافه نشده است.",
                parse_mode="HTML", reply_markup=await back_to_menu(),
            )
        await callback.answer()
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    for guide in guides:
        if guide["media_type"] == "TEXT" and guide.get("body"):
            await callback.message.answer(
                guide["body"],
                parse_mode="HTML",
            )
        elif guide["media_type"] == "PHOTO" and guide.get("file_id"):
            await callback.message.answer_photo(
                photo=guide["file_id"],
                caption=guide.get("body") or "",
                parse_mode="HTML" if guide.get("body") else None,
            )
        elif guide["media_type"] == "VIDEO" and guide.get("file_id"):
            await callback.message.answer_video(
                video=guide["file_id"],
                caption=guide.get("body") or "",
                parse_mode="HTML" if guide.get("body") else None,
            )
        elif guide["media_type"] == "DOCUMENT" and guide.get("file_id"):
            await callback.message.answer_document(
                document=guide["file_id"],
                caption=guide.get("body") or "",
                parse_mode="HTML" if guide.get("body") else None,
            )

    from keyboards.user import _btn
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [await _btn("📖 انتخاب پلتفرم دیگر", "guides", "link", btn_id="back")],
        [await _btn("🏠 بازگشت به منو", "main_menu", btn_id="back")],
    ])
    await callback.message.answer(
        "✅ پایان راهنما",
        reply_markup=kb,
    )
    await callback.answer()
