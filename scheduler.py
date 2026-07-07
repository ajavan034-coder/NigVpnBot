import asyncio
import logging
import os
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_notified_today: set[int] = set()
_last_reset_date: str = ""
_last_backup_time: float = 0


async def _deactivate_expired():
    from database import get_expired_active_configs, deactivate_config
    configs = await get_expired_active_configs()
    if configs:
        for c in configs:
            await deactivate_config(c["id"])
        logger.info("Deactivated %d expired configs", len(configs))


async def _send_expiry_reminders(bot):
    global _notified_today, _last_reset_date

    from database import get_setting
    enabled = await get_setting("expiry_reminder_enabled")
    if enabled == "0":
        return

    today = datetime.utcnow().strftime("%Y-%m-%d")
    if today != _last_reset_date:
        _notified_today.clear()
        _last_reset_date = today

    from database import get_configs_expiring_soon
    configs = await get_configs_expiring_soon()
    for c in configs:
        uid = c["user_id"]
        if uid in _notified_today:
            continue

        expire = datetime.fromisoformat(c["expire_date"])
        days_left = max(1, (expire - datetime.utcnow()).days)
        symbol = "تومان"
        try:
            symbol = await get_setting("currency_symbol") or symbol
        except Exception:
            pass

        try:
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"\u23f0 <b>کانفیگ در حال انقضا</b>\n\n"
                    f"کانفیگ <b>#{c['id']}</b> شما در <b>{days_left} روز</b> منقضی می‌شود.\n"
                    f"برای ادامه اتصال، کانفیگ جدید بخرید!"
                ),
            )
            _notified_today.add(uid)
        except Exception:
            _notified_today.add(uid)


async def _send_backup(bot):
    global _last_backup_time
    now = datetime.utcnow().timestamp()
    if _last_backup_time and (now - _last_backup_time) < 12 * 3600:
        return

    from database import get_setting
    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        return

    try:
        from api import panel_api
        inbounds = await panel_api.get_inbounds()
        if not inbounds:
            logger.warning("No inbounds found for backup")
            return

        full_data = []
        for inbound in inbounds:
            detail = await panel_api.get_inbound(inbound["id"])
            if detail:
                full_data.append(detail)

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        backup_file = f"/tmp/3xui_backup_{now_str.replace(' ', '_').replace(':', '-')}.json"
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)

        from aiogram.types import FSInputFile
        file_size = os.path.getsize(backup_file)
        await bot.send_document(
            chat_id=channel_id,
            document=FSInputFile(backup_file, filename=f"3xui_backup_{now_str.replace(' ', '_').replace(':', '-')}.json"),
            caption=f"📦 <b>بکاپ پنل 3x-ui</b>\n\n🕐 {now_str} UTC\n📋 تعداد اینباند: {len(full_data)}\n💾 حجم: {file_size / 1024:.1f} KB",
            parse_mode="HTML",
        )
        os.remove(backup_file)
        _last_backup_time = now
        logger.info("3x-ui backup sent to channel %s", channel_id)
    except Exception as e:
        logger.error("Failed to send 3x-ui backup: %s", e)


async def scheduler_loop(bot, interval: int = 300):
    logger.info("Scheduler started (interval=%ds)", interval)
    while True:
        try:
            await _deactivate_expired()
            await _send_expiry_reminders(bot)
            await _send_backup(bot)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(interval)
