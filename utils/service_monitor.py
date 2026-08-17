import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def check_services():
    """Check all active configs for volume/time warnings and expiry."""
    from database import get_db, get_setting, has_service_notification, add_service_notification, get_panel

    enabled = await get_setting("service_monitor_enabled") or "0"
    if enabled != "1":
        return

    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT c.*, u.username FROM configs c LEFT JOIN users u ON c.user_id = u.id WHERE c.is_active = 1"
        )
        configs = [dict(r) for r in await cursor.fetchall()]
        await db.close()
    except Exception as e:
        logger.error(f"Service monitor DB error: {e}")
        return

    volume_warn_pct = float(await get_setting("volume_warning_percent") or "80")
    expiry_warn_hours = float(await get_setting("expiry_warning_hours") or "48")

    from api import PanelAPI

    for cfg in configs:
        if not cfg.get("email") or not cfg.get("panel_id"):
            continue
        try:
            panel = await get_panel(cfg["panel_id"])
            if not panel:
                continue

            api = PanelAPI(
                panel_url=panel["url"],
                panel_user=panel["username"],
                panel_pass=panel["password"],
                panel_id=panel["id"],
            )
            await api.login()

            traffic = await api.get_client_traffic(cfg["email"])
            await api.close()
            if not traffic:
                continue

            total_bytes = traffic.get("total_bytes", 0)
            used_bytes = traffic.get("used_bytes", 0)
            expiry_time = traffic.get("expiry_time", 0)

            total_gb = total_bytes / (1024 * 1024 * 1024) if total_bytes > 0 else 0
            used_gb = used_bytes / (1024 * 1024 * 1024) if used_bytes > 0 else 0

            if total_bytes > 0:
                used_pct = (used_bytes / total_bytes) * 100
                if used_pct >= volume_warn_pct:
                    event = f"VOLUME_{int(used_pct)}PCT"
                    if not await has_service_notification(cfg["email"], event):
                        if await add_service_notification(cfg["email"], cfg["user_id"], event):
                            _notify_user(cfg, f"⚠️ حجم سرویس شما به {int(used_pct)}% رسیده است. ({used_gb:.1f}/{total_gb:.1f} GB)")

            if expiry_time > 0:
                expire_dt = datetime.utcfromtimestamp(expiry_time / 1000)
                hours_left = (expire_dt - datetime.utcnow()).total_seconds() / 3600
                if 0 < hours_left < expiry_warn_hours:
                    event = f"TIME_{int(hours_left)}H"
                    if not await has_service_notification(cfg["email"], event):
                        if await add_service_notification(cfg["email"], cfg["user_id"], event):
                            _notify_user(cfg, f"⏰ سرویس شما {int(hours_left)} ساعت دیگر منقضی می‌شود.")

            if expiry_time > 0 and expiry_time < datetime.utcnow().timestamp() * 1000:
                if not await has_service_notification(cfg["email"], "EXPIRED"):
                    if await add_service_notification(cfg["email"], cfg["user_id"], "EXPIRED"):
                        _notify_user(cfg, "❌ سرویس شما منقضی شده است.")

            if total_bytes > 0 and used_bytes >= total_bytes:
                if not await has_service_notification(cfg["email"], "EXHAUSTED"):
                    if await add_service_notification(cfg["email"], cfg["user_id"], "EXHAUSTED"):
                        _notify_user(cfg, "❌ حجم سرویس شما تمام شده است.")

        except Exception as e:
            logger.error(f"Service monitor check error for {cfg.get('email')}: {e}")
            continue


def _notify_user(cfg: dict, message: str):
    """Send notification to user (non-blocking)."""
    try:
        import state
        bot = state.bot_instance
        if bot:
            asyncio.create_task(bot.send_message(cfg["user_id"], message))
    except Exception as e:
        logger.error(f"Failed to notify user {cfg.get('user_id')}: {e}")


async def monitor_loop():
    """Background loop that runs check_services periodically."""
    while True:
        try:
            from database import get_setting
            interval = int(await get_setting("service_monitor_interval") or "300")
        except Exception:
            interval = 300
        await asyncio.sleep(interval)
        try:
            await check_services()
        except Exception as e:
            logger.error(f"Service monitor error: {e}")
