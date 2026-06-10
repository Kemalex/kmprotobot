#!/usr/bin/env python3
"""
Telegram Proxy Bot — автоматический поиск и смена MTProto/SOCKS5 прокси.
Использует открытый источник: https://kort0881.github.io/telegram-proxy-collector/
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import settings
from handlers import common, proxy, admin
from services.scheduler import ProxyScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Запуск Telegram Proxy Bot...")

    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрация роутеров
    dp.include_router(common.router)
    dp.include_router(proxy.router)
    dp.include_router(admin.router)

    # Запуск планировщика автообновления
    scheduler = ProxyScheduler(bot, settings)
    await scheduler.start()

    logger.info("Бот запущен. Ожидание сообщений...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            scheduler=scheduler,
        )
    finally:
        await scheduler.stop()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
