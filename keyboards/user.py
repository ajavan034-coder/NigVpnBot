from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from database import get_setting, is_admin
from utils.premium_emoji import get_button_emoji_id


async def _btn(text: str, callback_data: str, emoji_name: str = None, style: str = None, btn_id: str = None) -> InlineKeyboardButton:
    kwargs = {"text": text, "callback_data": callback_data}
    if btn_id:
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
        elif style:
            kwargs["style"] = style
    elif emoji_name:
        from utils.premium_emoji import get_button_emoji_id
        eid = await get_button_emoji_id(emoji_name)
        if eid:
            kwargs["icon_custom_emoji_id"] = eid
        if style:
            kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


async def _url_btn(btn_id: str, url: str, emoji_name: str, default_style: str = "") -> InlineKeyboardButton:
    text = await get_setting(f"btn_{btn_id}") or btn_id.replace("_", " ").title()
    kwargs = {"text": text, "url": url}
    db_emoji = await get_setting(f"btn_emoji_{btn_id}")
    if db_emoji:
        kwargs["icon_custom_emoji_id"] = db_emoji
    elif emoji_name:
        eid = await get_button_emoji_id(emoji_name)
        if eid:
            kwargs["icon_custom_emoji_id"] = eid
    db_style = await get_setting(f"btn_style_{btn_id}")
    if db_style:
        kwargs["style"] = db_style
    elif default_style:
        kwargs["style"] = default_style
    return InlineKeyboardButton(**kwargs)


async def main_menu(user_id: int = 0) -> InlineKeyboardMarkup:
    import json

    raw = await get_setting("menu_layout") or "[]"
    try:
        layout = json.loads(raw)
    except Exception:
        layout = []

    if not layout:
        default_order = [
            {"type": "builtin", "id": "wallet", "enabled": True},
            {"type": "row_break"},
            {"type": "builtin", "id": "free_test", "enabled": True},
            {"type": "builtin", "id": "buy_config", "enabled": True},
            {"type": "row_break"},
            {"type": "builtin", "id": "my_configs", "enabled": True},
            {"type": "builtin", "id": "invite", "enabled": True},
            {"type": "builtin", "id": "collab", "enabled": True},
            {"type": "row_break"},
            {"type": "builtin", "id": "webapp", "enabled": True},
            {"type": "builtin", "id": "admin", "enabled": True},
        ]
        layout = default_order

    has_collab = any(item.get("id") == "collab" for item in layout if item.get("type") == "builtin")
    if not has_collab:
        new_layout = []
        for item in layout:
            new_layout.append(item)
            if item.get("type") == "builtin" and item.get("id") == "invite":
                new_layout.append({"type": "builtin", "id": "collab", "enabled": True})
        if not any(item.get("id") == "collab" for item in new_layout if item.get("type") == "builtin"):
            insert_idx = len(new_layout) - 1
            new_layout.insert(insert_idx, {"type": "builtin", "id": "collab", "enabled": True})
            if insert_idx > 0 and new_layout[insert_idx - 1].get("type") != "row_break":
                new_layout.insert(insert_idx, {"type": "row_break"})
        layout = new_layout

    async def make_builtin_btn(bid):
        if bid == "wallet":
            return await _btn(await get_setting("btn_wallet"), "wallet", "wallet", "primary", "wallet")
        elif bid == "free_test":
            return await _btn(await get_setting("btn_free_test"), "free_test", "free_test", "primary", "free_test")
        elif bid == "buy_config":
            return await _btn(await get_setting("btn_buy_config"), "buy_config", "buy_config", "primary", "buy_config")
        elif bid == "my_configs":
            return await _btn(await get_setting("btn_my_configs"), "my_configs", "my_configs", "success", "my_configs")
        elif bid == "channel":
            url = await get_setting("channel_url") or ""
            if not url:
                return None
            return await _url_btn("channel", url, "link", "primary")
        elif bid == "support":
            url = await get_setting("support_url") or ""
            if not url:
                return None
            return await _url_btn("support", url, "owner", "")
        elif bid == "admin":
            return await _btn(await get_setting("btn_admin_settings") or "Admin", "adm_menu", "settings", "", "admin_settings")
        elif bid == "invite":
            enabled = await get_setting("invite_enabled")
            if enabled != "1":
                return None
            return await _btn(await get_setting("btn_invite") or "زیر مجموعه گیری", "invite", "link", "success", "invite")
        elif bid == "collab":
            enabled = await get_setting("collab_enabled")
            if enabled != "1":
                return None
            from database import get_user
            user = await get_user(user_id) if user_id else None
            if user and user.get("is_collaborator"):
                return None
            return await _btn(await get_setting("btn_collab_request") or "🤝 درخواست همکاری", "collab_request", "link", "primary", "collab_request")
        elif bid == "webapp":
            url = "https://nigcity.ir/app"
            return InlineKeyboardButton(text="🌐 Open Panel", web_app=WebAppInfo(url=url))
        return None

    current_row = []
    rows = []
    for item in layout:
        if item.get("type") == "row_break":
            if current_row:
                rows.append(current_row)
                current_row = []
            continue
        if item.get("type") == "builtin":
            bid = item.get("id", "")
            if not item.get("enabled", True):
                continue
            if bid == "free_test" and await get_setting("free_test_enabled") != "1":
                continue
            if bid == "admin" and not (user_id and await is_admin(user_id)):
                continue
            btn = await make_builtin_btn(bid)
            if btn:
                current_row.append(btn)
        elif item.get("type") == "custom":
            text = item.get("text", "")
            url = item.get("url", "")
            if not text or not url:
                continue
            kwargs = {"text": text, "url": url}
            if item.get("emoji_id"):
                kwargs["icon_custom_emoji_id"] = item["emoji_id"]
            if item.get("style"):
                kwargs["style"] = item["style"]
            current_row.append(InlineKeyboardButton(**kwargs))

    if current_row:
        rows.append(current_row)

    if not rows:
        rows = [
            [await _btn(await get_setting("btn_wallet"), "wallet", "wallet", "primary", "wallet")],
            [await _btn(await get_setting("btn_buy_config"), "buy_config", "buy_config", "primary", "buy_config")],
            [await _btn(await get_setting("btn_my_configs"), "my_configs", "my_configs", "success", "my_configs")],
        ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def wallet_menu() -> InlineKeyboardMarkup:
    topup = await get_setting("btn_topup")
    tx_history = await get_setting("btn_tx_history")
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn(topup, "topup", "money", btn_id="topup")],
            [await _btn(tx_history, "tx_history", "history", btn_id="tx_history")],
            [await _btn(back, "main_menu", "back", btn_id="back")],
        ]
    )


async def payment_method_menu(plan_id: int, discounted_price: float = None, discount_label: str = None) -> InlineKeyboardMarkup:
    wallet_btn = await get_setting("btn_wallet_payment") or "Pay with Wallet"
    c2c_btn = await get_setting("btn_c2c_payment") or "Card to Card"
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn(wallet_btn, f"pay_wallet_{plan_id}", "card", btn_id="wallet_payment")],
            [await _btn(c2c_btn, f"pay_c2c_{plan_id}", "card", btn_id="c2c_payment")],
            [await _btn("🏷️ اعمال کد تخفیف", f"apply_discount_{plan_id}", "link", btn_id="apply_discount")],
            [await _btn(back, "buy_config", "back", btn_id="back2")],
        ]
    )


async def name_selection_menu(plan_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("✏️ نام دلخواه", f"name_custom_{plan_id}", "link", btn_id="name_custom")],
            [await _btn("🎲 نام تصادفی", f"name_random_{plan_id}", "link", btn_id="name_random")],
            [await _btn(back, "buy_config", "back", btn_id="back2")],
        ]
    )


async def sections_menu() -> InlineKeyboardMarkup:
    from database import get_plan_sections, get_panel
    sections = await get_plan_sections()
    buttons = []
    _panel_cache = {}
    for s in sections:
        btn = await _btn(s["name"], f"select_section_{s['id']}", "link", btn_id="plan_name")
        panel_id = s.get("panel_id")
        if panel_id:
            if panel_id not in _panel_cache:
                _panel_cache[panel_id] = await get_panel(panel_id)
            panel = _panel_cache[panel_id]
            if panel and panel.get("emoji_id"):
                btn.icon_custom_emoji_id = panel["emoji_id"]
        buttons.append([btn])
    back = await get_setting("btn_back")
    buttons.append([await _btn(back, "main_menu", "back", btn_id="back3")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def plans_menu(section_id: int = None) -> InlineKeyboardMarkup:
    from database import get_plans, get_panel
    plans = await get_plans()
    if section_id:
        plans = [p for p in plans if p.get("section_id") == section_id]
    symbol = await get_setting("currency_symbol") or "تومان"
    buttons = []
    _panel_cache = {}
    for p in plans:
        name_text = f"{p['name']} | {p['gb']}GB" if not p.get('is_ultimate') else p['name']
        price_text = f"{p['price']:,} {symbol}"
        name_btn = await _btn(name_text, f"select_plan_{p['id']}", "package", btn_id="plan_name")
        panel_id = p.get("panel_id")
        if panel_id:
            if panel_id not in _panel_cache:
                _panel_cache[panel_id] = await get_panel(panel_id)
            panel = _panel_cache[panel_id]
            if panel and panel.get("emoji_id"):
                name_btn.icon_custom_emoji_id = panel["emoji_id"]
        price_btn = await _btn(price_text, f"select_plan_{p['id']}", "money", btn_id="plan_price")
        buttons.append([name_btn, price_btn])
    back = await get_setting("btn_back")
    buttons.append([await _btn(back, "buy_config", "back", btn_id="back3")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def config_detail(config_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("Copy Sub Link", f"copy_link_{config_id}", "copy", btn_id="copy_link")],
            [await _btn(back, "my_configs", "back", btn_id="back4")],
        ]
    )


async def service_detail_keyboard(config_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                await _btn("کپی لینک", f"copy_link_{config_id}", btn_id="service_copy_link"),
                await _btn("تغییر لینک", f"regen_link_{config_id}", btn_id="service_change_link"),
            ],
            [
                await _btn("حجم سرویس", f"volume_info_{config_id}", btn_id="service_volume"),
                await _btn("خرید حجم", f"buy_extra_{config_id}", btn_id="service_buy_extra"),
            ],
            [
                await _btn("کانفیگ‌ها", f"extract_configs_{config_id}", btn_id="service_extract"),
            ],
            [await _btn("بازگشت", "my_configs", btn_id="back")],
        ]
    )


async def extra_volume_keyboard(config_id: int, price_per_gb: int) -> InlineKeyboardMarkup:
    from database import get_setting
    symbol = await get_setting("currency_symbol") or "تومان"
    options = [5, 10, 20, 50]
    buttons = []
    row = []
    for gb in options:
        price = gb * price_per_gb
        btn = await _btn(f"{gb}GB - {price:,} {symbol}", f"confirm_extra_{config_id}_{gb}", btn_id="service_confirm_extra")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([await _btn("بازگشت", f"config_detail_{config_id}", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def regenerate_link_keyboard(config_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("تأیید", f"confirm_regen_{config_id}", btn_id="service_confirm_regenerate")],
            [await _btn("لغو", f"config_detail_{config_id}", btn_id="cancel")],
        ]
    )


async def force_join_keyboard(channel_id: str) -> InlineKeyboardMarkup:
    join_text = await get_setting("force_join_btn_join") or "🔗 عضویت در کانال"
    check_text = await get_setting("force_join_btn_check") or "✅ بررسی عضویت"
    check_btn = await _btn(check_text, "check_membership", "check", btn_id="force_join_check")

    url = None
    if channel_id.startswith("@"):
        url = f"https://t.me/{channel_id.lstrip('@')}"
    elif channel_id.startswith("-"):
        try:
            import state
            if state.bot_instance:
                chat = await state.bot_instance.get_chat(channel_id)
                if chat.username:
                    url = f"https://t.me/{chat.username}"
        except Exception:
            pass
    else:
        url = f"https://t.me/{channel_id}"

    buttons = []
    if url:
        join_kwargs = {"text": join_text, "url": url}
        eid = await get_button_emoji_id("link")
        if eid:
            join_kwargs["icon_custom_emoji_id"] = eid
        db_style = await get_setting("btn_style_force_join_join")
        if db_style:
            join_kwargs["style"] = db_style
        buttons.append([InlineKeyboardButton(**join_kwargs)])
    buttons.append([check_btn])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def back_to_menu() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back_to_menu")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn(back, "main_menu", "back", btn_id="back_to_menu")]
        ]
    )


BUTTON_CONFIGS = {
    "start": {"label": "Start", "default_style": "", "default_emoji": "start"},
    "wallet": {"label": "Wallet", "default_style": "primary", "default_emoji": "wallet"},
    "free_test": {"label": "Free Test", "default_style": "primary", "default_emoji": "free_test"},
    "buy_config": {"label": "Buy Config", "default_style": "primary", "default_emoji": "buy_config"},
    "my_configs": {"label": "My Configs", "default_style": "success", "default_emoji": "my_configs"},
    "invite": {"label": "Referral", "default_style": "success", "default_emoji": "link"},
    "invite_copy": {"label": "Copy Invite Link", "default_style": "", "default_emoji": "copy"},
    "topup": {"label": "Top Up", "default_style": "", "default_emoji": "money"},
    "tx_history": {"label": "Transaction History", "default_style": "", "default_emoji": "history"},
    "back": {"label": "Back", "default_style": "", "default_emoji": "back"},
    "back_to_menu": {"label": "Back to Menu", "default_style": "", "default_emoji": "back"},
    "wallet_payment": {"label": "Pay with Wallet", "default_style": "", "default_emoji": "card"},
    "c2c_payment": {"label": "Card to Card", "default_style": "", "default_emoji": "card"},
    "copy_link": {"label": "Copy Link", "default_style": "", "default_emoji": "copy"},
    "copy_number": {"label": "Copy Card Number", "default_style": "", "default_emoji": "copy_number"},
    "copy_price": {"label": "Copy Price", "default_style": "", "default_emoji": "copy_price"},
    "c2c_confirm": {"label": "Payment Success (C2C)", "default_style": "success", "default_emoji": "success"},
    "topup_confirm": {"label": "Payment Success (TopUp)", "default_style": "success", "default_emoji": "success"},
    "cancel": {"label": "Cancel", "default_style": "danger", "default_emoji": "cancel"},
    "make_config": {"label": "Make My Config", "default_style": "primary", "default_emoji": "package"},
    "force_join_join": {"label": "Join Channel", "default_style": "primary", "default_emoji": "link"},
    "force_join_check": {"label": "Check Membership", "default_style": "success", "default_emoji": "check"},
    "admin_stats": {"label": "Admin - Statistics", "default_style": "", "default_emoji": "stats"},
    "admin_receipts": {"label": "Admin - Receipts", "default_style": "", "default_emoji": "receipts"},
    "admin_users": {"label": "Admin - Users", "default_style": "", "default_emoji": "users"},
    "admin_settings": {"label": "Admin - Settings", "default_style": "", "default_emoji": "settings"},
    "admin_admins": {"label": "Admin - Admins", "default_style": "", "default_emoji": "admins"},
    "admin_plans": {"label": "Admin - Plans", "default_style": "", "default_emoji": "plans"},
    "admin_broadcast": {"label": "Admin - Broadcast", "default_style": "", "default_emoji": "list"},
    "admin_panel_info": {"label": "Admin - Panel Info", "default_style": "", "default_emoji": "gear"},
    "approve": {"label": "Approve Receipt", "default_style": "success", "default_emoji": "approve"},
    "reject": {"label": "Reject Receipt", "default_style": "danger", "default_emoji": "reject"},
    "add_balance": {"label": "Add Balance", "default_style": "success", "default_emoji": "plus"},
    "remove_balance": {"label": "Remove Balance", "default_style": "danger", "default_emoji": "minus"},
    "ban": {"label": "Ban User", "default_style": "danger", "default_emoji": "ban"},
    "unban": {"label": "Unban User", "default_style": "success", "default_emoji": "unban"},
    "view_configs": {"label": "View Configs", "default_style": "", "default_emoji": "list"},
    "add_admin": {"label": "Add Admin", "default_style": "success", "default_emoji": "plus"},
    "remove_admin": {"label": "Remove Admin", "default_style": "danger", "default_emoji": "minus"},
    "list_admins": {"label": "List Admins", "default_style": "", "default_emoji": "list"},
    "add_plan": {"label": "Add Plan", "default_style": "success", "default_emoji": "plus"},
    "edit_plan": {"label": "Edit Plan", "default_style": "", "default_emoji": "gear"},
    "delete_plan": {"label": "Delete Plan", "default_style": "danger", "default_emoji": "cross"},
    "edit_welcome": {"label": "Edit Welcome Text", "default_style": "", "default_emoji": "gear"},
    "edit_buttons": {"label": "Edit Button Names", "default_style": "", "default_emoji": "gear"},
    "edit_currency": {"label": "Change Currency", "default_style": "", "default_emoji": "gear"},
    "edit_card_number": {"label": "Card Number", "default_style": "", "default_emoji": "card"},
    "edit_card_owner": {"label": "Card Owner Name", "default_style": "", "default_emoji": "owner"},
    "edit_free_test_mb": {"label": "Free Test Volume", "default_style": "", "default_emoji": "gear"},
    "toggle_free_test": {"label": "Toggle Free Test", "default_style": "", "default_emoji": "gear"},
    "edit_auto_approve": {"label": "Auto-Approve Limit", "default_style": "", "default_emoji": "gear"},
    "edit_premium_emojis": {"label": "Premium Emojis", "default_style": "", "default_emoji": "gear"},
    "send_emoji_register": {"label": "Send Premium Emoji", "default_style": "", "default_emoji": "star"},
    "view_emojis": {"label": "View Registered Emojis", "default_style": "", "default_emoji": "list"},
    "clear_emojis": {"label": "Clear All Emojis", "default_style": "danger", "default_emoji": "cross"},
    "channel": {"label": "Channel", "default_style": "primary", "default_emoji": "link"},
    "support": {"label": "Support", "default_style": "", "default_emoji": "owner"},
    "plan_name": {"label": "Plan Name", "default_style": "primary", "default_emoji": "package"},
    "plan_price": {"label": "Plan Price", "default_style": "success", "default_emoji": "money"},
    "service_copy_link": {"label": "Copy Link", "default_style": "", "default_emoji": "copy"},
    "service_change_link": {"label": "Change Link", "default_style": "primary", "default_emoji": "link"},
    "service_volume": {"label": "Volume Info", "default_style": "", "default_emoji": "package"},
    "service_buy_extra": {"label": "Buy Extra", "default_style": "success", "default_emoji": "plus"},
    "service_confirm_extra": {"label": "Confirm Purchase", "default_style": "success", "default_emoji": "approve"},
    "service_confirm_regenerate": {"label": "Confirm", "default_style": "success", "default_emoji": "approve"},
    "service_extract": {"label": "Extract Configs", "default_style": "", "default_emoji": "link"},
    "view_user_details": {"label": "View User Details", "default_style": "", "default_emoji": "owner"},
}




async def my_services_panel_menu(user_id: int) -> InlineKeyboardMarkup:
    """Show panels that have user's active configs."""
    from database import get_user_configs, get_panel
    configs = await get_user_configs(user_id)
    active_configs = [c for c in configs if c.get("is_active")]
    
    # Group configs by panel_id
    panel_configs = {}
    for cfg in active_configs:
        panel_id = cfg.get("panel_id")
        if panel_id is None:
            # Fallback: get panel_id from plan
            from database import get_plan
            plan = await get_plan(cfg.get("plan_id"))
            panel_id = plan.get("panel_id") if plan else None
        if panel_id:
            panel_configs.setdefault(panel_id, []).append(cfg)
    
    buttons = []
    _panel_cache = {}
    for panel_id, cfgs in panel_configs.items():
        if panel_id not in _panel_cache:
            _panel_cache[panel_id] = await get_panel(panel_id)
        panel = _panel_cache[panel_id]
        if panel:
            panel_name = panel["name"]
            count = len(cfgs)
            btn = await _btn(f"{panel_name} ({count})", f"my_services_panel_{panel_id}", "package", btn_id="plan_name")
            if panel.get("emoji_id"):
                btn.icon_custom_emoji_id = panel["emoji_id"]
            buttons.append([btn])
    
    if not buttons:
        buttons.append([await _btn("سرویسی یافت نشد", "noop", "package", btn_id="plan_name")])
    
    back = await get_setting("btn_back")
    buttons.append([await _btn(back, "main_menu", "back", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def my_services_configs_menu(user_id: int, panel_id: int) -> InlineKeyboardMarkup:
    """Show configs for a specific panel."""
    from database import get_user_configs, get_panel
    configs = await get_user_configs(user_id)
    active_configs = [c for c in configs if c.get("is_active") and c.get("panel_id") == panel_id]

    if not active_configs:
        from database import get_plan
        for c in [c for c in configs if c.get("is_active")]:
            plan = await get_plan(c.get("plan_id"))
            if plan and plan.get("panel_id") == panel_id:
                active_configs.append(c)

    buttons = []
    for cfg in active_configs[:10]:
        svc_name = cfg.get("config_name") or f"سرویس #{cfg['id']}"
        from utils.texts import to_jalali
        expire = to_jalali(cfg.get("expire_date", ""))
        buttons.append([InlineKeyboardButton(
            text=f"🟢 {svc_name} — انقضا: {expire}",
            callback_data=f"config_detail_{cfg['id']}",
        )])

    buttons.append([await _btn("🔍 کانفیگم رو پیدا نمی‌کنم!", f"recover_config_{panel_id}", "link", btn_id="back")])

    back = await get_setting("btn_back")
    buttons.append([await _btn(back, "my_configs", "back", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def view_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 مشاهده پروفایل کاربر", url=f"https://t.me/NigVpnBot?start=view_user_{user_id}")],
    ])
