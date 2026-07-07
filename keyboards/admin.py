from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_setting
from keyboards.user import _btn


async def admin_menu() -> InlineKeyboardMarkup:
    stats = await get_setting("btn_admin_stats")
    receipts = await get_setting("btn_admin_receipts")
    users = await get_setting("btn_admin_users")
    settings = await get_setting("btn_admin_settings")
    admins = await get_setting("btn_admin_admins")
    plans = await get_setting("btn_admin_plans") or "Plans"
    broadcast = await get_setting("btn_admin_broadcast") or "Broadcast"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn(stats, "admin_stats", "stats", btn_id="admin_stats")],
            [await _btn(plans, "admin_plans", "plans", btn_id="admin_plans")],
            [await _btn(receipts, "pending_receipts", "receipts", btn_id="admin_receipts")],
            [await _btn(users, "admin_users", "users", btn_id="admin_users")],
            [await _btn("Panel Info", "panel_info", "gear", btn_id="admin_panel_info")],
            [await _btn(broadcast, "admin_broadcast", "list", btn_id="admin_broadcast")],
            [await _btn(settings, "admin_settings", "settings", btn_id="admin_settings")],
            [await _btn(admins, "manage_admins", "admins", btn_id="admin_admins")],
        ]
    )


async def receipt_actions(receipt_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                await _btn("Approve", f"approve_{receipt_id}", "approve", "success", "approve"),
                await _btn("Reject", f"reject_{receipt_id}", "reject", "danger", "reject"),
            ],
            [await _btn(back, "admin_menu", "back", btn_id="back")],
        ]
    )


async def user_actions(user_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("View Configs", f"admin_cfgs_{user_id}", "list", btn_id="view_configs")],
            [
                await _btn("+ Add Balance", f"add_bal_{user_id}", "plus", "success", "add_balance"),
                await _btn("- Remove Balance", f"rem_bal_{user_id}", "minus", "danger", "remove_balance"),
            ],
            [
                await _btn("Ban", f"ban_{user_id}", "ban", "danger", "ban"),
                await _btn("Unban", f"unban_{user_id}", "unban", "success", "unban"),
            ],
            [await _btn(back, "admin_users", "back", btn_id="back")],
        ]
    )


async def admin_settings_menu() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    free_test_status = await get_setting("free_test_enabled")
    ft_label = "Disable Free Test" if free_test_status == "1" else "Enable Free Test"
    ft_callback = "toggle_free_test"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("Edit Welcome Text", "edit_welcome", "gear", btn_id="edit_welcome")],
            [await _btn("Edit Button Names", "edit_buttons", "gear", btn_id="edit_buttons")],
            [await _btn("Change Currency Symbol", "edit_currency", "gear", btn_id="edit_currency")],
            [await _btn("Card Number", "edit_card_number", "card", btn_id="edit_card_number")],
            [await _btn("Card Owner Name", "edit_card_owner", "owner", btn_id="edit_card_owner")],
            [await _btn("Free Test Volume", "edit_free_test_mb", "gear", btn_id="edit_free_test_mb")],
            [await _btn(ft_label, ft_callback, "gear", btn_id="toggle_free_test")],
            [await _btn("Auto-Approve Limit", "edit_auto_approve", "gear", btn_id="edit_auto_approve")],
            [await _btn("Premium Emojis", "edit_premium_emojis", "star", btn_id="edit_premium_emojis")],
            [await _btn(back, "admin_menu", "back", btn_id="back")],
        ]
    )


async def buttons_menu() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    btn_wallet = await get_setting("btn_wallet")
    btn_free_test = await get_setting("btn_free_test")
    btn_buy = await get_setting("btn_buy_config")
    btn_configs = await get_setting("btn_my_configs")
    btn_topup = await get_setting("btn_topup")
    btn_history = await get_setting("btn_tx_history")
    btn_back_menu = await get_setting("btn_back_to_menu")
    btn_stats = await get_setting("btn_admin_stats")
    btn_receipts = await get_setting("btn_admin_receipts")
    btn_users = await get_setting("btn_admin_users")
    btn_settings = await get_setting("btn_admin_settings")
    btn_admins = await get_setting("btn_admin_admins")
    btn_plans = await get_setting("btn_admin_plans")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Wallet: {btn_wallet}", callback_data="edit_btn_wallet")],
            [InlineKeyboardButton(text=f"Free Test: {btn_free_test}", callback_data="edit_btn_free_test")],
            [InlineKeyboardButton(text=f"Buy Config: {btn_buy}", callback_data="edit_btn_buy_config")],
            [InlineKeyboardButton(text=f"My Configs: {btn_configs}", callback_data="edit_btn_my_configs")],
            [InlineKeyboardButton(text=f"Top Up: {btn_topup}", callback_data="edit_btn_topup")],
            [InlineKeyboardButton(text=f"History: {btn_history}", callback_data="edit_btn_tx_history")],
            [InlineKeyboardButton(text=f"Back: {back}", callback_data="edit_btn_back")],
            [InlineKeyboardButton(text=f"Back Menu: {btn_back_menu}", callback_data="edit_btn_back_to_menu")],
            [InlineKeyboardButton(text=f"Stats: {btn_stats}", callback_data="edit_btn_admin_stats")],
            [InlineKeyboardButton(text=f"Receipts: {btn_receipts}", callback_data="edit_btn_admin_receipts")],
            [InlineKeyboardButton(text=f"Users: {btn_users}", callback_data="edit_btn_admin_users")],
            [InlineKeyboardButton(text=f"Settings: {btn_settings}", callback_data="edit_btn_admin_settings")],
            [InlineKeyboardButton(text=f"Admins: {btn_admins}", callback_data="edit_btn_admin_admins")],
            [InlineKeyboardButton(text=f"Plans: {btn_plans}", callback_data="edit_btn_admin_plans")],
            [await _btn(back, "admin_settings", "back", btn_id="back")],
        ]
    )


async def plans_management_menu() -> InlineKeyboardMarkup:
    from database import get_all_plans
    plans = await get_all_plans()
    symbol = await get_setting("currency_symbol") or "تومان"
    buttons = []
    for p in plans:
        status = "+" if p["is_active"] else "x"
        buttons.append([InlineKeyboardButton(
            text=f"[{status}] {p['name']} | {p['gb']}GB | {p['days']}D | {p['price']:,} {symbol}",
            callback_data=f"plan_detail_{p['id']}",
        )])
    buttons.append([await _btn("+ Add Plan", "add_plan", "plus", "success", "add_plan")])
    back = await get_setting("btn_back")
    buttons.append([await _btn(back, "admin_menu", "back", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def plan_actions(plan_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("Edit Plan", f"edit_plan_{plan_id}", "gear", btn_id="edit_plan")],
            [await _btn("Delete Plan", f"delete_plan_{plan_id}", "cross", "danger", "delete_plan")],
            [await _btn(back, "admin_plans", "back", btn_id="back")],
        ]
    )


async def back_to_admin() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn(back, "admin_menu", "back", btn_id="back")]
        ]
    )


async def manage_admins_menu() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("+ Add Admin", "add_admin", "plus", "success", "add_admin")],
            [await _btn("- Remove Admin", "remove_admin", "minus", "danger", "remove_admin")],
            [await _btn("List Admins", "list_admins", "list", btn_id="list_admins")],
            [await _btn(back, "admin_menu", "back", btn_id="back")],
        ]
    )


async def premium_emojis_menu() -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("Send Premium Emoji", "send_emoji_register", "star", btn_id="send_emoji_register")],
            [await _btn("View Registered Emojis", "view_emojis", "list", btn_id="view_emojis")],
            [await _btn("Clear All Emojis", "clear_emojis", "cross", "danger", "clear_emojis")],
            [await _btn(back, "admin_settings", "back", btn_id="back")],
        ]
    )


async def user_config_list(configs: list, user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for c in configs[:10]:
        status = "Active" if c["is_active"] else "Expired"
        buttons.append([InlineKeyboardButton(
            text=f"Config #{c['id']} ({status})",
            callback_data=f"admin_cfg_{c['id']}_{user_id}",
        )])
    back = await get_setting("btn_back")
    buttons.append([await _btn(back, f"view_user_{user_id}", "back", btn_id="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def config_detail_actions(config_id: int, user_id: int) -> InlineKeyboardMarkup:
    back = await get_setting("btn_back")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [await _btn("Delete Config", f"admin_del_cfg_{config_id}_{user_id}", "cross", "danger", "delete_plan")],
            [await _btn(back, f"admin_cfgs_{user_id}", "back", btn_id="back")],
        ]
    )
