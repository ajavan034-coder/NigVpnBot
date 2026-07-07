import re
from database import get_setting, set_setting
import json


async def load_emoji_ids() -> dict:
    raw = await get_setting("premium_emojis")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}


async def save_emoji_ids(mapping: dict):
    await set_setting("premium_emojis", json.dumps(mapping))


async def register_premium_emoji(name: str, custom_emoji_id: str):
    mapping = await load_emoji_ids()
    mapping[name] = custom_emoji_id
    await save_emoji_ids(mapping)


async def get_available_emojis() -> dict:
    defaults = {
        "wallet": "\U0001f4b3",
        "free_test": "\U0001f195",
        "buy_config": "\U0001f6d2",
        "my_configs": "\U0001f4cb",
        "back": "\u2b05\ufe0f",
        "admin": "\U0001f6e0\ufe0f",
        "stats": "\U0001f4ca",
        "users": "\U0001f465",
        "settings": "\u2699\ufe0f",
        "plans": "\U0001f4c8",
        "receipts": "\U0001f4cb",
        "admins": "\U0001f511",
        "check": "\u2705",
        "cross": "\u274c",
        "card": "\U0001f4b3",
        "owner": "\U0001f464",
        "star": "\u2b50",
        "copy": "\U0001f517",
        "cancel": "\u274c",
        "success": "\u2705",
        "reject": "\u274c",
        "approve": "\u2705",
        "ban": "\U0001f6ab",
        "unban": "\u2705",
        "plus": "\u2795",
        "minus": "\u2796",
        "list": "\U0001f4cb",
        "gear": "\u2699\ufe0f",
        "money": "\U0001f4b0",
        "calendar": "\U0001f4c5",
        "history": "\U0001f4ca",
        "menu": "\U0001f35f",
        "package": "\U0001f4e6",
        "link": "\U0001f517",
        "clock": "\u23f3",
        "start": "\u25b6\ufe0f",
        "copy_number": "\U0001f4cb",
        "copy_price": "\U0001f4b0",
    }
    return defaults


async def pe(name: str) -> str:
    eid = await get_button_emoji_id(name)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">🔹</tg-emoji>'
    emojis = await get_available_emojis()
    return emojis.get(name, "")


async def get_button_emoji_id(name: str) -> str | None:
    mapping = await load_emoji_ids()
    return mapping.get(name) or None
