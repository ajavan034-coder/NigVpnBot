from utils.premium_emoji import pe


async def _get_text(key, default):
    from database import get_setting
    return await get_setting(key) or default


WELCOME_TEXT_DEFAULT = "به NigVpn خوش آمدید! خرید آسان و امن VPN"


async def wallet_text(balance: float, symbol: str = "تومان") -> str:
    e = await pe("money")
    tpl = await _get_text("text_wallet",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>کیف پول من</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  موجودی: <b>{{balance}} {symbol}</b>\n\n"
        f"  رسید پرداخت آپلود کنید تا کیف پول شارژ شود."
    )
    return tpl.replace("{balance}", f"{balance:,.0f}")


async def receipt_submitted(amount: float, symbol: str = "تومان") -> str:
    e = await pe("success")
    tpl = await _get_text("text_receipt_submitted",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>رسید ارسال شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  مبلغ: <b>{{amount}} {symbol}</b>\n"
        f"  وضعیت: <b>در انتظار بررسی</b>\n\n"
        f"  ادمین رسید شما را بررسی خواهد کرد."
    )
    return tpl.replace("{amount}", f"{amount:,.0f}")


async def receipt_approved(amount: float, new_balance: float, symbol: str = "تومان") -> str:
    e = await pe("success")
    tpl = await _get_text("text_receipt_approved",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>رسید تایید شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  اضافه شده: <b>{{amount}} {symbol}</b>\n"
        f"  موجودی جدید: <b>{{new_balance}} {symbol}</b>"
    )
    return tpl.replace("{amount}", f"{amount:,.0f}").replace("{new_balance}", f"{new_balance:,.0f}")


async def receipt_rejected(amount: float, symbol: str = "تومان") -> str:
    e = await pe("reject")
    tpl = await _get_text("text_receipt_rejected",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>رسید رد شد</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  مبلغ: <b>{{amount}} {symbol}</b>\n\n"
        f"  برای اطلاعات بیشتر با ادمین تماس بگیرید."
    )
    return tpl.replace("{amount}", f"{amount:,.0f}")


async def config_created(sub_link: str, expire_date: str, price: int, plan_name: str, gb: int, days: int, symbol: str = "تومان") -> str:
    ep = await pe("package")
    eh = await pe("calendar")
    em = await pe("money")
    ec = await pe("clock")
    el = await pe("link")
    tpl = await _get_text("text_config_created",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {ep} کانفیگ ساخته شد!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📦 پلن: {{plan_name}}\n"
        f"  📊 حجم: {{gb}} GB\n"
        f"  {eh} مدت: {{days}} روز\n"
        f"  {em} پرداخت: {{price}} {symbol}\n"
        f"  {ec} انقضا:{{expire_date}}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} لینک اشتراک:\n"
        f"<code>{{sub_link}}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"QR کد را اسکن کنید یا لینک بالا را کپی نمایید."
    )
    return (tpl
        .replace("{plan_name}", plan_name)
        .replace("{gb}", str(gb))
        .replace("{days}", str(days))
        .replace("{price}", f"{price:,}")
        .replace("{expire_date}", expire_date)
        .replace("{sub_link}", sub_link)
    )


async def free_test_config(sub_link: str, days: int) -> str:
    ef = await pe("free_test")
    tpl = await _get_text("text_free_test",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {ef} کانفیگ تست رایگان\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📊 حجم: 100 مگابایت\n"
        f"  📅 مدت: {{days}} روز\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  🔗 لینک اشتراک:\n"
        f"<code>{{sub_link}}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"QR کد را اسکن کنید یا لینک بالا را کپی نمایید.\n\n"
        f"<i>این تست رایگان شماست. برای ادامه، کانفیگ کامل بخرید.</i>"
    )
    return tpl.replace("{days}", str(days)).replace("{sub_link}", sub_link)


async def no_balance(price: int, balance: float, symbol: str = "تومان") -> str:
    e = await pe("cross")
    tpl = await _get_text("text_no_balance",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>موجودی ناکافی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  قیمت کانفیگ: <b>{{price}} {symbol}</b>\n"
        f"  موجودی شما: <b>{{balance}} {symbol}</b>\n\n"
        f"  ابتدا کیف پول خود را شارژ کنید."
    )
    return tpl.replace("{price}", f"{price:,}").replace("{balance}", f"{balance:,.0f}")


async def config_list_text(configs: list[dict]) -> str:
    el = await pe("list")
    ec = await pe("check")
    er = await pe("cross")
    if not configs:
        tpl = await _get_text("text_config_list_empty",
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  {el} <b>کانفیگ‌های من</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  کانفیگ فعالی ندارید.\n"
            f"  برای شروع، کانفیگ بخرید!"
        )
        return tpl
    tpl = await _get_text("text_config_list",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} <b>کانفیگ‌های من</b> ({{count}})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    text = tpl.replace("{count}", str(len(configs)))
    for i, cfg in enumerate(configs, 1):
        status = ec if cfg["is_active"] else er
        text += f"  {status} کانفیگ #{cfg['id']} — انقضا: {cfg['expire_date'][:10]}\n"
    return text


async def admin_stats(user_count: int, config_count: int, revenue: float, pending: int, symbol: str = "تومان") -> str:
    es = await pe("stats")
    eu = await pe("users")
    em = await pe("money")
    er = await pe("receipts")
    tpl = await _get_text("text_admin_stats",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {es} <b>آمار ادمین</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {eu} کل کاربران: <b>{{user_count}}</b>\n"
        f"  🔑 کانفیگ‌های فعال: <b>{{config_count}}</b>\n"
        f"  {em} درآمد کل: <b>{{revenue}} {symbol}</b>\n"
        f"  {er} رسیدهای در انتظار: <b>{{pending}}</b>"
    )
    return (tpl
        .replace("{user_count}", str(user_count))
        .replace("{config_count}", str(config_count))
        .replace("{revenue}", f"{revenue:,.0f}")
        .replace("{pending}", str(pending))
    )


async def receipt_info(receipt: dict, symbol: str = "تومان") -> str:
    er = await pe("receipts")
    eu = await pe("users")
    em = await pe("money")
    ec = await pe("calendar")
    tpl = await _get_text("text_receipt_info",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {er} <b>رسید #{{receipt_id}}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {eu} کاربر: @{{username}} ({{user_id}})\n"
        f"  {em} مبلغ: <b>{{amount}} {symbol}</b>\n"
        f"  {ec} تاریخ: {{created_at}}\n"
        f"  📌 وضعیت: <b>{{status}}</b>"
    )
    return (tpl
        .replace("{receipt_id}", str(receipt['id']))
        .replace("{username}", receipt.get('username', 'N/A'))
        .replace("{user_id}", str(receipt['user_id']))
        .replace("{amount}", f"{receipt['amount']:,.0f}")
        .replace("{created_at}", receipt['created_at'])
        .replace("{status}", receipt['status'])
    )


async def user_info(user: dict, symbol: str = "تومان") -> str:
    eu = await pe("owner")
    em = await pe("money")
    ec = await pe("calendar")
    banned_text = "بله" if user["is_banned"] else "خیر"
    tpl = await _get_text("text_user_info",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {eu} <b>اطلاعات کاربر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  آیدی: <code>{{user_id}}</code>\n"
        f"  نام کاربری: @{{username}}\n"
        f"  نام: {{first_name}}\n"
        f"  {em} موجودی: <b>{{balance}} {symbol}</b>\n"
        f"  {ec} تاریخ ثبت: {{created_at}}\n"
        f"  🔒 مسدود: {{banned}}"
    )
    return (tpl
        .replace("{user_id}", str(user['id']))
        .replace("{username}", user.get('username', 'N/A'))
        .replace("{first_name}", user.get('first_name', 'N/A'))
        .replace("{balance}", f"{user['balance']:,.0f}")
        .replace("{created_at}", user['created_at'])
        .replace("{banned}", banned_text)
    )


async def enter_amount() -> str:
    em = await pe("money")
    return await _get_text("text_enter_amount",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {em} <b>شارژ کیف پول</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  مبلغ را وارد کنید (مثال: 50000):"
    )


async def setting_updated(key: str, value: str) -> str:
    eg = await pe("gear")
    tpl = await _get_text("text_setting_updated",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {eg} <b>تنظیم به‌روزرسانی شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {{key}}: <b>{{value}}</b>"
    )
    return tpl.replace("{key}", key).replace("{value}", value)


async def confirm_approve(amount: float) -> str:
    e = await pe("approve")
    tpl = await _get_text("text_confirm_approve", f"{e} تایید رسید به مبلغ {{amount}}؟")
    return tpl.replace("{amount}", f"{amount:,.0f}")


async def confirm_reject() -> str:
    e = await pe("reject")
    return await _get_text("text_confirm_reject", f"{e} رد این رسید؟")


async def no_pending_receipts() -> str:
    e = await pe("check")
    return await _get_text("text_no_pending",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>رسید در انتظاری وجود ندارد</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


BOT_TEXTS = {
    "text_wallet": ("Wallet Text", "کیف پول من", "{balance} = موجودی کاربر"),
    "text_receipt_submitted": ("Receipt Submitted", "رسید ارسال شد", "{amount} = مبلغ"),
    "text_receipt_approved": ("Receipt Approved", "رسید تایید شد", "{amount} = مبلغ, {new_balance} = موجودی جدید"),
    "text_receipt_rejected": ("Receipt Rejected", "رسید رد شد", "{amount} = مبلغ"),
    "text_config_created": ("Config Created", "کانفیگ ساخته شد", "{plan_name} {gb} {days} {price} {expire_date} {sub_link}"),
    "text_free_test": ("Free Test Config", "کانفیگ تست رایگان", "{days} {sub_link}"),
    "text_no_balance": ("No Balance", "موجودی ناکافی", "{price} {balance}"),
    "text_config_list_empty": ("My Configs (Empty)", "کانفیگ‌های من - خالی", "بدون متغیر"),
    "text_config_list": ("My Configs (List)", "کانفیگ‌های من", "{count} = تعداد"),
    "text_admin_stats": ("Admin Stats", "آمار ادمین", "{user_count} {config_count} {revenue} {pending}"),
    "text_receipt_info": ("Receipt Info", "اطلاعات رسید", "{receipt_id} {username} {user_id} {amount} {created_at} {status}"),
    "text_user_info": ("User Info", "اطلاعات کاربر", "{user_id} {username} {first_name} {balance} {created_at} {banned}"),
    "text_enter_amount": ("Enter Amount", "شارژ کیف پول", "بدون متغیر"),
    "text_setting_updated": ("Setting Updated", "تنظیم به‌روزرسانی شد", "{key} {value}"),
    "text_confirm_approve": ("Confirm Approve", "تایید رسید", "{amount}"),
    "text_confirm_reject": ("Confirm Reject", "رد رسید", "بدون متغیر"),
    "text_no_pending": ("No Pending Receipts", "رسید در انتظاری وجود ندارد", "بدون متغیر"),
    "text_topup_card": ("Top Up - Card Info", "شارژ کیف پول - اطلاعات کارت", "{amount} {card_number} {card_owner}"),
    "text_topup_upload_photo": ("Top Up - Upload Photo", "آپلود رسید پرداخت", "بدون متغیر"),
    "text_c2c_payment": ("C2C Payment", "پرداخت کارت به کارت", "{plan_name} {gb} {days} {amount} {card_number} {card_owner}"),
    "text_c2c_upload_photo": ("C2C Upload Photo", "آپلود رسید کارت به کارت", "بدون متغیر"),
    "text_c2c_receipt_submitted": ("C2C Receipt Submitted", "رسید کارت به کارت ارسال شد", "{plan_name} {gb} {days} {amount}"),
    "text_service_list": ("My Services (List)", "سرویس‌های من", "{count} = تعداد سرویس‌ها"),
    "text_service_list_empty": ("My Services (Empty)", "سرویس‌های من - خالی", "بدون متغیر"),
    "text_service_detail": ("Service Detail", "جزئیات سرویس", "{config_id} {plan_name} {expire_date} {total_gb} {used_gb} {remaining_gb} {sub_link}"),
    "text_buy_extra_volume": ("Buy Extra Volume", "خرید حجم اضافی", "{plan_name} {current_total_gb} {extra_gb} {total_price} {symbol}"),
    "text_extra_volume_success": ("Extra Volume Success", "حجم اضافی فعال شد", "{extra_gb} {new_total_gb}"),
    "text_no_balance_extra": ("No Balance for Extra", "موجودی ناکافی برای حجم اضافی", "{price} {balance}"),
    "text_regenerate_link_confirm": ("Regenerate Link Confirm", "تأیید بازسازی لینک", "بدون متغیر"),
    "text_regenerate_link_success": ("Regenerate Link Success", "لینک جدید ساخته شد", "{new_link}"),
    "text_volume_detail": ("Volume Detail", "جزئیات حجم", "{config_id}"),
    "text_extract_configs": ("Extract Configs", "استخراج کانفیگ‌ها", "{config_id}"),
    "text_new_user_notification": ("New User Notification", "اعلام کاربر جدید", "{username} {user_id} {first_name} {today} {week} {month} {lifetime}"),
}


async def c2c_payment_text(plan, symbol, card_number, card_owner):
    e = await pe("card")
    tpl = await _get_text("text_c2c_payment",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>پرداخت کارت به کارت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📦 پلن: <b>{{plan_name}}</b>\n"
        f"  📊 حجم: <b>{{gb}} GB</b>\n"
        f"  📅 مدت: <b>{{days}} روز</b>\n"
        f"  💰 مبلغ: <b>{{amount}} {symbol}</b>\n\n"
        f"  شماره کارت: <code>{{card_number}}</code>\n"
        f"  صاحب کارت: <b>{{card_owner}}</b>\n\n"
        f"  مبلغ دقیق را به کارت بالا واریز کنید،\n"
        f"  سپس روی <b>پرداخت موفق</b> کلیک کنید\n"
        f"  و رسید خود را آپلود کنید."
    )
    return (tpl
        .replace("{plan_name}", plan['name'])
        .replace("{gb}", str(plan['gb']))
        .replace("{days}", str(plan['days']))
        .replace("{amount}", f"{plan['price']:,}")
        .replace("{card_number}", card_number)
        .replace("{card_owner}", card_owner)
    )


async def c2c_upload_photo_text():
    e = await pe("success")
    return await _get_text("text_c2c_upload_photo",
        f"{e} <b>رسید پرداخت خود را آپلود کنید.</b>"
    )


async def c2c_receipt_submitted_text(plan, symbol):
    e = await pe("success")
    tpl = await _get_text("text_c2c_receipt_submitted",
        f"{e} <b>رسید با موفقیت ارسال شد!</b>\n\n"
        f"  📦 پلن: <b>{{plan_name}}</b> ({{gb}}GB / {{days}} روز)\n"
        f"  💰 مبلغ: <b>{{amount}} {symbol}</b>\n\n"
        f"  ادمین‌ها رسید شما را بررسی خواهند کرد.\n"
        f"  پس از تأیید، کانفیگ شما به صورت خودکار ارسال می‌شود."
    )
    return (tpl
        .replace("{plan_name}", plan['name'])
        .replace("{gb}", str(plan['gb']))
        .replace("{days}", str(plan['days']))
        .replace("{amount}", f"{plan['price']:,}")
    )


async def service_list_text(configs: list[dict]) -> str:
    el = await pe("list")
    ec = await pe("check")
    er = await pe("cross")
    if not configs:
        tpl = await _get_text("text_service_list_empty",
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  {el} <b>سرویس‌های من</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  شما سرویس فعالی ندارید.\n"
            f"  برای شروع، سرویس بخرید!"
        )
        return tpl
    tpl = await _get_text("text_service_list",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} <b>سرویس‌های من</b> ({{count}})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    text = tpl.replace("{count}", str(len(configs)))
    for cfg in configs:
        status = ec if cfg["is_active"] else er
        text += f"  {status} سرویس #{cfg['id']} — انقضا: {cfg['expire_date'][:10]}\n"
    return text


async def service_detail_text(config_id: int, plan_name: str, expire_date: str, sub_link: str, traffic_info: dict | None = None) -> str:
    ep = await pe("package")
    eh = await pe("calendar")
    el = await pe("link")
    tpl = await _get_text("text_service_detail",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {ep} <b>سرویس #{config_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📦 پلن: <b>{{plan_name}}</b>\n"
        f"  {eh} انقضا: <b>{{expire_date}}</b>\n\n"
    )
    if traffic_info:
        tpl += (
            f"  📊 حجم کل: <b>{{total_gb}} GB</b>\n"
            f"  📈 مصرف شده: <b>{{used_gb}} GB</b>\n"
            f"  📉 باقی‌مانده: <b>{{remaining_gb}} GB</b>\n\n"
        )
        tpl = (tpl
            .replace("{total_gb}", str(traffic_info["total_gb"]))
            .replace("{used_gb}", str(traffic_info["used_gb"]))
            .replace("{remaining_gb}", str(traffic_info["remaining_gb"]))
        )
    tpl += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} <b>لینک اشتراک:</b>\n"
        f"<code>{{sub_link}}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"QR کد را اسکن کنید یا لینک بالا را کپی نمایید."
    )
    return (tpl
        .replace("{plan_name}", plan_name)
        .replace("{expire_date}", expire_date)
        .replace("{sub_link}", sub_link)
    )


async def buy_extra_volume_text(plan_name: str, current_total_gb: float, extra_gb: int, price_per_gb: int, symbol: str = "تومان") -> str:
    ep = await pe("package")
    em = await pe("money")
    total_price = extra_gb * price_per_gb
    tpl = await _get_text("text_buy_extra_volume",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {em} <b>خرید حجم اضافی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {ep} پلن: <b>{{plan_name}}</b>\n"
        f"  📊 حجم فعلی: <b>{{current_total_gb}} GB</b>\n"
        f"  ➕ حجم اضافی: <b>{{extra_gb}} GB</b>\n"
        f"  💰 قیمت هر GB: <b>{price_per_gb:,} {symbol}</b>\n"
        f"  💰 مبلغ کل: <b>{{total_price}} {symbol}</b>\n\n"
        f"  آیا مایل به خرید هستید؟"
    )
    return (tpl
        .replace("{plan_name}", plan_name)
        .replace("{current_total_gb}", str(current_total_gb))
        .replace("{extra_gb}", str(extra_gb))
        .replace("{total_price}", f"{total_price:,}")
    )


async def extra_volume_success_text(extra_gb: int, new_total_gb: float) -> str:
    e = await pe("success")
    tpl = await _get_text("text_extra_volume_success",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>حجم اضافی فعال شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  ➕ اضافه شده: <b>{{extra_gb}} GB</b>\n"
        f"  📊 حجم جدید: <b>{{new_total_gb}} GB</b>\n\n"
        f"  اکنون می‌توانید از سرویس خود استفاده کنید."
    )
    return (tpl
        .replace("{extra_gb}", str(extra_gb))
        .replace("{new_total_gb}", str(new_total_gb))
    )


async def no_balance_for_extra(price: int, balance: float, symbol: str = "تومان") -> str:
    e = await pe("cross")
    tpl = await _get_text("text_no_balance_extra",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>موجودی ناکافی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  هزینه: <b>{{price}} {symbol}</b>\n"
        f"  موجودی شما: <b>{{balance}} {symbol}</b>\n\n"
        f"  ابتدا کیف پول خود را شارژ کنید."
    )
    return tpl.replace("{price}", f"{price:,}").replace("{balance}", f"{balance:,.0f}")


async def regenerate_link_confirm_text() -> str:
    e = await pe("gear")
    tpl = await _get_text("text_regenerate_link_confirm",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>بازسازی لینک اشتراک</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  با بازسازی لینک، لینک قدومی غیرفعال می‌شود\n"
        f"  و لینک جدیدی برای شما ساخته می‌شود.\n\n"
        f"  آیا مطمئن هستید؟"
    )
    return tpl


async def regenerate_link_success_text(new_link: str) -> str:
    e = await pe("success")
    el = await pe("link")
    tpl = await _get_text("text_regenerate_link_success",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {e} <b>لینک جدید ساخته شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  {el} <b>لینک جدید:</b>\n"
        f"<code>{{new_link}}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"QR کد را اسکن کنید یا لینک بالا را کپی نمایید."
    )
    return tpl.replace("{new_link}", new_link)


async def volume_detail_text(config_id: int, plan_name: str, traffic_info: dict) -> str:
    el = await pe("list")
    tpl = await _get_text("text_volume_detail",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} <b>جزئیات حجم سرویس #{config_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  📦 پلن: <b>{plan_name}</b>\n\n"
        f"  📊 حجم کل: <b>{traffic_info['total_gb']} GB</b>\n"
        f"  ⬆️ آپلود: <b>{traffic_info['used_gb'] / 2:.2f} GB</b>\n"
        f"  ⬇️ دانلود: <b>{traffic_info['used_gb'] / 2:.2f} GB</b>\n"
        f"  📈 مصرف کل: <b>{traffic_info['used_gb']} GB</b>\n"
        f"  📉 باقی‌مانده: <b>{traffic_info['remaining_gb']} GB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return tpl


async def extract_configs_text(config_id: int, client_configs: list) -> str:
    el = await pe("list")
    tpl = await _get_text("text_extract_configs",
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"  {el} <b>کانفیگ‌های سرویس #{config_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    if not client_configs:
        tpl += f"  کانفیگی یافت نشد.\n"
    else:
        for i, cc in enumerate(client_configs, 1):
            tpl += f"  📡 <b>{cc['tag']}</b> ({cc['protocol']})\n"
            tpl += f"  <code>{cc['config_link']}</code>\n\n"
    tpl += f"━━━━━━━━━━━━━━━━━━━━"
    return tpl
