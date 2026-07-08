import asyncio
import logging
import threading
import os
from dotenv import load_dotenv

load_dotenv()

# Validate environment before doing anything
from validate_env import validate_env
if not os.getenv("SKIP_ENV_VALIDATION"):
    if not validate_env():
        exit(1)


def run_web():
    from web_app import app
    from config import WEB_HOST, WEB_PORT
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


async def run_bot():
    from logging.handlers import RotatingFileHandler
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from config import BOT_TOKEN, LOG_LEVEL
    from database import init_db
    from handlers.user import router as user_router
    from handlers.wallet import router as wallet_router
    from handlers.admin import router as admin_router
    from handlers.callback import router as callback_router
    from middlewares import BanCheckMiddleware, RateLimitMiddleware
    from api import panel_api

    # Setup logging — use journald (stdout) when under systemd, file+console otherwise
    log_level = getattr(logging, LOG_LEVEL, logging.INFO)
    log_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    handlers = []
    if os.getenv("INVOCATION_ID") or os.path.exists("/run/systemd/system"):
        # Running under systemd — log to stdout only
        console = logging.StreamHandler()
        console.setFormatter(log_format)
        handlers.append(console)
    else:
        # Running standalone — log to file + console
        file_handler = RotatingFileHandler(
            "bot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(log_format)
        handlers.append(file_handler)
        console = logging.StreamHandler()
        console.setFormatter(log_format)
        handlers.append(console)

    logging.basicConfig(level=log_level, handlers=handlers)
    logger = logging.getLogger("vpnbot")

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Check your .env file.")
        return

    await init_db()
    panel_api.reload_config()
    logger.info("Database initialized. Panel URL: %s, Inbound IDs: %s", panel_api.panel_url, panel_api.inbound_ids)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    import state
    state.bot_instance = bot
    state.loop_instance = asyncio.get_running_loop()
    dp = Dispatcher()

    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    dp.include_router(user_router)
    dp.include_router(wallet_router)
    dp.include_router(admin_router)
    dp.include_router(callback_router)

    logger.info("Bot starting polling...")
    from scheduler import scheduler_loop
    sched_task = asyncio.create_task(scheduler_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        sched_task.cancel()
        await panel_api.close()
        await bot.session.close()


if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    from config import WEB_PORT
    print(f"Web dashboard: http://localhost:{WEB_PORT}")
    asyncio.run(run_bot())
