from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_user, add_receipt, get_setting, get_admins
from keyboards.user import wallet_menu, back_to_menu
from utils.texts import wallet_text, receipt_submitted, enter_amount

router = Router()


class TopUpState(StatesGroup):
    waiting_amount = State()
    waiting_photo = State()


@router.callback_query(F.data == "wallet")
async def cb_wallet(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("لطفاً ابتدا /start را بزنید", show_alert=True)
        return
    symbol = await get_setting("currency_symbol") or "تومان"
    text = await wallet_text(user["balance"], symbol)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await wallet_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=await wallet_menu())


@router.callback_query(F.data == "topup")
async def cb_topup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopUpState.waiting_amount)
    await callback.message.edit_text(
        await enter_amount(),
        reply_markup=await back_to_menu(),
    )


@router.message(TopUpState.waiting_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("مبلغ نامعتبر. یک عدد مثبت وارد کنید (مثال: 50000):")
        return

    min_topup = float(await get_setting("min_topup") or "50000")
    if amount < min_topup:
        symbol = await get_setting("currency_symbol") or "تومان"
        await message.answer(f"حداقل شارژ {min_topup:,.0f} {symbol} است. دوباره تلاش کنید:")
        return

    await state.update_data(amount=amount)
    await state.set_state(TopUpState.waiting_photo)
    symbol = await get_setting("currency_symbol") or "تومان"
    card_number = await get_setting("card_number") or "1234-5678-9012-3456"
    card_owner = await get_setting("card_owner") or "Card Owner"
    from utils.premium_emoji import pe, get_button_emoji_id
    from utils.texts import _get_text

    ec = await pe("card")

    tpl = await _get_text("text_topup_card",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {ec} <b>شارژ کیف پول</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  مبلغ: <b>{{amount}} {symbol}</b>\n\n"
        f"  شماره کارت: <code>{{card_number}}</code>\n"
        f"  صاحب کارت: <b>{{card_owner}}</b>\n\n"
        f"  مبلغ دقیق را به کارت بالا واریز کنید،\n"
        f"  سپس روی <b>پرداخت موفق</b> کلیک کنید\n"
        f"  و رسید خود را آپلود کنید."
    )
    text = (tpl
        .replace("{amount}", f"{amount:,.0f}")
        .replace("{card_number}", card_number)
        .replace("{card_owner}", card_owner)
    )

    copy_card_btn = InlineKeyboardButton(
        text="کپی شماره کارت",
        copy_text=CopyTextButton(text=card_number),
    )
    eid = await get_button_emoji_id("copy_number")
    if eid:
        copy_card_btn.icon_custom_emoji_id = eid

    copy_both_btn = InlineKeyboardButton(
        text="کپی مبلغ",
        copy_text=CopyTextButton(text=f"{amount:,.0f} {symbol}"),
    )
    eid = await get_button_emoji_id("copy_price")
    if eid:
        copy_both_btn.icon_custom_emoji_id = eid

    from keyboards.user import _btn
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [copy_card_btn, copy_both_btn],
        [await _btn("پرداخت موفق", "topup_confirm", "success", btn_id="topup_confirm")],
        [await _btn("لغو", "main_menu", "cancel", "danger", "cancel")],
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "topup_confirm")
async def cb_topup_confirm(callback: CallbackQuery, state: FSMContext):
    from utils.premium_emoji import pe
    e = await pe("success")
    from utils.texts import _get_text
    text = await _get_text("text_topup_upload_photo",
        f"{e} <b>رسید پرداخت خود را آپلود کنید.</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=await back_to_menu())


@router.message(TopUpState.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    photo_file_id = message.photo[-1].file_id

    receipt_id = await add_receipt(message.from_user.id, amount, photo_file_id, plan_id=0)
    await state.clear()
    symbol = await get_setting("currency_symbol") or "تومان"

    auto_max = float(await get_setting("auto_approve_max") or "0")
    if auto_max > 0 and amount <= auto_max:
        from database import approve_receipt, get_pending_receipts
        pending = await get_pending_receipts()
        receipt = None
        for r in pending:
            if r["user_id"] == message.from_user.id and abs(r["amount"] - amount) < 0.01:
                receipt = r
                break
        if receipt:
            await approve_receipt(receipt["id"], 0)
            user = await get_user(message.from_user.id)
            new_balance = user["balance"] if user else 0
            from utils.texts import receipt_approved
            await message.answer(
                await receipt_approved(amount, new_balance, symbol),
                reply_markup=await back_to_menu(),
            )
        else:
            await message.answer(
                await receipt_submitted(amount, symbol),
                reply_markup=await back_to_menu(),
            )
    else:
        await message.answer(
            await receipt_submitted(amount, symbol),
            reply_markup=await back_to_menu(),
        )

    from handlers.user import _send_receipt_to_channel
    await _send_receipt_to_channel(
        message.bot, photo_file_id,
        f"**New Receipt** (Top Up)\n\n"
        f"User: @{message.from_user.username or 'N/A'} (ID: {message.from_user.id})\n"
        f"Amount: {amount:,.0f} {symbol}\n\n"
        f"Use /admin to review.",
        receipt_id=receipt_id,
    )


@router.callback_query(F.data == "cancel_receipt")
async def cb_cancel_receipt(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("رسید لغو شد.", reply_markup=await back_to_menu())


@router.callback_query(F.data == "tx_history")
async def cb_tx_history(callback: CallbackQuery):
    from database import get_db
    symbol = await get_setting("currency_symbol") or "تومان"
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM receipts WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (callback.from_user.id,),
    )
    receipts = await cursor.fetchall()
    await db.close()

    if not receipts:
        await callback.message.edit_text(
            "**تاریخچه تراکنش**\n\nهیچ تراکنشی ثبت نشده.",
            parse_mode="Markdown",
            reply_markup=await back_to_menu(),
        )
        return

    text = "**تاریخچه تراکنش**\n\n"
    for r in receipts:
        status_icon = {"pending": "در انتظار", "approved": "تایید شده", "rejected": "رد شده"}.get(r["status"], "نامشخص")
        text += f"{status_icon} {r['amount']:,.0f} {symbol} ({r['created_at'][:10]})\n"

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=await back_to_menu())
