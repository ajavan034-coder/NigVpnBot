import asyncio
import logging
import os
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_last_backup_time: float = 0
_last_backup_date: str = ""


async def _deactivate_expired(bot=None):
    from database import get_expired_active_configs, deactivate_config, get_setting
    configs = await get_expired_active_configs()
    if configs:
        notify = await get_setting("expired_config_notify")
        for c in configs:
            await deactivate_config(c["id"])
            if bot and notify != "0":
                uid = c["user_id"]
                cfg_name = c.get("config_name") or f"#{c['id']}"
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            f"\u274c <b>کانفیگ منقضی شد</b>\n\n"
                            f"کانفیگ <b>{cfg_name}</b> شما منقضی شده و غیرفعال شد.\n"
                            f"برای ادامه اتصال، کانفیگ جدید بخرید!"
                        ),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning("Failed to notify user %d about expired config: %s", uid, e)
        logger.info("Deactivated %d expired configs", len(configs))


async def _send_expiry_reminders(bot):
    from database import get_setting
    enabled = await get_setting("expiry_reminder_enabled")
    if enabled == "0":
        return

    from database import get_configs_expiring_in_24h, get_configs_expiring_in_1h, has_notified, mark_notified

    configs_24h = await get_configs_expiring_in_24h()
    for c in configs_24h:
        uid = c["user_id"]
        cfg_id = c["id"]
        if await has_notified(uid, cfg_id, "24h"):
            continue

        cfg_name = c.get("config_name") or f"#{cfg_id}"
        try:
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"\u23f0 <b>کانفیگ در حال انقضا</b>\n\n"
                    f"کانفیگ <b>{cfg_name}</b> شما در کمتر از ۲۴ ساعت منقضی می\u200cشود.\n"
                    f"برای ادامه اتصال، کانفیگ جدید بخرید!"
                ),
                parse_mode="HTML",
            )
            await mark_notified(uid, cfg_id, "24h")
        except Exception:
            await mark_notified(uid, cfg_id, "24h")

    configs_1h = await get_configs_expiring_in_1h()
    for c in configs_1h:
        uid = c["user_id"]
        cfg_id = c["id"]
        if await has_notified(uid, cfg_id, "1h"):
            continue

        cfg_name = c.get("config_name") or f"#{cfg_id}"
        try:
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"\u23f0 <b>کانفیگ در حال انقضا</b>\n\n"
                    f"کانفیگ <b>{cfg_name}</b> شما در کمتر از ۱ ساعت منقضی می\u200cشود!\n"
                    f"برای ادامه اتصال، کانفیگ جدید بخرید!"
                ),
                parse_mode="HTML",
            )
            await mark_notified(uid, cfg_id, "1h")
        except Exception:
            await mark_notified(uid, cfg_id, "1h")
async def _backup_3xui_panel(panel, channel_id, bot, panel_name=""):
    """Backup a single 3x-ui panel and send .db file to channel."""
    try:
        db_path = await panel.backup_database()
        if not db_path or not os.path.exists(db_path):
            logger.warning("3x-ui backup returned no file for panel %s", panel.panel_id)
            return False

        from aiogram.types import FSInputFile
        file_size = os.path.getsize(db_path)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        filename = os.path.basename(db_path)

        await bot.send_document(
            chat_id=channel_id,
            document=FSInputFile(db_path, filename=filename),
            caption=(
                f"📦 <b>Backup for {panel_name}</b>\n\n"
                f"🕐 {now_str} UTC\n"
                f"💾 حجم: {file_size / 1024:.1f} KB\n"
                f"📋 فرمت: SQLite Database (.db)"
            ),
            parse_mode="HTML",
        )
        os.remove(db_path)
        logger.info("3x-ui backup sent for panel '%s'", panel_name)
        return True
    except Exception as e:
        logger.error("Failed to backup 3x-ui panel '%s': %s", panel_name, e)
        return False


async def _backup_wireguard_panel(panel_url, channel_id, bot, panel_id=None, panel_name=""):
    """Backup a Wireguard/Azumi panel and send .db file to channel."""
    try:
        from wireguard_api import WireguardAPI
        wg = WireguardAPI(panel_url)
        db_path = await wg.backup_database()
        await wg.close()

        if not db_path or not os.path.exists(db_path):
            logger.warning("Wireguard backup returned no file for panel '%s'", panel_name)
            return False

        from aiogram.types import FSInputFile
        file_size = os.path.getsize(db_path)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        filename = os.path.basename(db_path)

        await bot.send_document(
            chat_id=channel_id,
            document=FSInputFile(db_path, filename=filename),
            caption=(
                f"📦 <b>Backup for {panel_name}</b>\n\n"
                f"🕐 {now_str} UTC\n"
                f"💾 حجم: {file_size / 1024:.1f} KB\n"
                f"📋 فرمت: SQLite Database (.db)"
            ),
            parse_mode="HTML",
        )
        os.remove(db_path)
        logger.info("Wireguard backup sent for panel '%s'", panel_name)
        return True
    except Exception as e:
        logger.error("Failed to backup Wireguard panel '%s': %s", panel_name, e)
        return False


async def _send_backup(bot):
    global _last_backup_time, _last_backup_date

    from database import get_setting

    enabled = await get_setting("backup_enabled")
    if enabled == "0":
        return

    channel_id = await get_setting("notification_channel_id") or ""
    if not channel_id:
        logger.debug("Backup skipped: no notification_channel_id set")
        return

    backup_hour = int(await get_setting("backup_hour") or "4")
    backup_minute = int(await get_setting("backup_minute") or "0")

    now = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    if _last_backup_date == today_str:
        logger.debug("Backup already sent today (%s)", today_str)
        return

    time_match = (now.hour == backup_hour and now.minute == backup_minute)
    past_scheduled = (now.hour > backup_hour) or (now.hour == backup_hour and now.minute > backup_minute)

    if not time_match and not past_scheduled:
        logger.debug("Backup waiting: current %02d:%02d, scheduled %02d:%02d", now.hour, now.minute, backup_hour, backup_minute)
        return

    from database import get_active_panels
    panels = await get_active_panels()
    logger.info("Backup check: %d active panels, channel=%s, time=%02d:%02d", len(panels), channel_id, now.hour, now.minute)

    if not panels:
        logger.warning("No active panels found for backup")
        return

    logger.info("Starting scheduled backup for %d panels", len(panels))

    success_count = 0
    fail_count = 0
    for p in panels:
        ptype = (p.get("panel_type") or "v2ray").strip().lower()
        purl = p.get("url", "")
        pid = p.get("id")
        pname = p.get("name", f"Panel #{pid}")

        logger.info("Backing up panel '%s' (id=%s, type=%s)", pname, pid, ptype)

        try:
            if ptype in ("wireguard", "azumi", "wg"):
                ok = await _backup_wireguard_panel(purl, channel_id, bot, panel_id=pid, panel_name=pname)
            else:
                from api import PanelAPI
                panel_api_instance = PanelAPI(
                    panel_url=purl,
                    panel_user=p.get("username", ""),
                    panel_pass=p.get("password", ""),
                    panel_id=pid,
                )
                ok = await _backup_3xui_panel(panel_api_instance, channel_id, bot, panel_name=pname)
                await panel_api_instance.close()

            if ok:
                success_count += 1
            else:
                fail_count += 1
                logger.warning("Backup returned false for panel '%s'", pname)
        except Exception as e:
            fail_count += 1
            logger.error("Exception backing up panel '%s': %s", pname, e)

    _last_backup_time = now.timestamp()
    _last_backup_date = today_str
    logger.info("Scheduled backup completed: %d success, %d failed out of %d total", success_count, fail_count, len(panels))


async def _retry_unsent_receipts(bot):
    try:
        from database import get_unsent_receipts, mark_receipt_sent, get_user, get_plan_name
        from handlers.user import _send_receipt_to_channel
        unsent = await get_unsent_receipts()
        if not unsent:
            return

        logger.info("Retrying %d unsent receipts to channel", len(unsent))
        for receipt in unsent[:10]:
            try:
                user = await get_user(receipt["user_id"])
                plan_name = await get_plan_name(receipt.get("plan_id"))
                uname = f"@{user.get('username')}" if user and user.get("username") else str(receipt["user_id"])
                symbol = "تومان"
                try:
                    from database import get_setting
                    symbol = await get_setting("currency_symbol") or symbol
                except Exception:
                    pass
                caption = (
                    f"**رسید پرداخت**\n\n"
                    f"کاربر: {uname} (ID: {receipt['user_id']})\n"
                    f"پلن: {plan_name}\n"
                    f"مبلغ: {receipt['amount']:,.0f} {symbol}\n"
                    f"وضعیت: در انتظار بررسی\n\n"
                    f"Use /admin to review."
                )
                await _send_receipt_to_channel(
                    bot, receipt["photo_file_id"], caption, receipt_id=receipt["id"]
                )
            except Exception as e:
                logger.error("Failed to retry receipt %s: %s", receipt["id"], e)
    except Exception as e:
        logger.error("Error in _retry_unsent_receipts: %s", e)


async def scheduler_loop(bot, interval: int = 60):
    logger.info("Scheduler started (interval=%ds)", interval)
    while True:
        try:
            await _deactivate_expired(bot)
            await _send_expiry_reminders(bot)
            await _send_backup(bot)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(interval)
