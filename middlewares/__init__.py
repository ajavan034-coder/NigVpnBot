import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database import is_admin, get_user


class AdminMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            data["is_admin"] = await is_admin(user_id)
        return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            user = await get_user(user_id)
            if user and user.get("is_banned"):
                if isinstance(event, Message):
                    await event.answer("🚫 You are banned from using this bot.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 You are banned.", show_alert=True)
                return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, cooldown: float = 1.0):
        self.cooldown = cooldown
        self.last_click: dict[int, float] = {}
        self._last_cleanup: float = time.time()

    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            now = time.time()

            # Periodic cleanup: evict entries older than 60s every 30s
            if now - self._last_cleanup > 30:
                self._last_cleanup = now
                stale = [uid for uid, ts in self.last_click.items() if now - ts > 60]
                for uid in stale:
                    del self.last_click[uid]

            last = self.last_click.get(user_id, 0)
            if now - last < self.cooldown:
                await event.answer("Slow down!", show_alert=True)
                return None
            self.last_click[user_id] = now
        return await handler(event, data)
