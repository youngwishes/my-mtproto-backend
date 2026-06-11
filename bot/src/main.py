from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher

from bot import bot
from router import main_router

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    dp = Dispatcher()
    dp.include_router(main_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен пользователем")
