import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import init_db
from handlers.user import router as user_router
from handlers.wallet import router as wallet_router
from handlers.admin import router as admin_router
from handlers.callback import router as callback_router
from middlewares import AdminMiddleware, BanCheckMiddleware, RateLimitMiddleware
from api import panel_api


async def main():
    from logging.handlers import RotatingFileHandler
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler = RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    logger = logging.getLogger(__name__)

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Check your .env file.")
        return

    await init_db()
    panel_api.reload_config()
    logger.info(f"Database initialized. Panel URL: {panel_api.panel_url}, Inbound IDs: {panel_api.inbound_ids}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
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
    asyncio.run(main())
