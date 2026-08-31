import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.config import settings
from src.custom_emoji import PremiumEmojiMiddleware

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
bot.session.middleware(PremiumEmojiMiddleware())
dp = Dispatcher()


async def main():
    from src.dependencies import build_dependencies
    from src.error_handler import register_error_handler
    from src.handlers import router

    await bot.delete_webhook(drop_pending_updates=True)

    dp.include_router(router)
    register_error_handler(dp)
    dp["deps"] = build_dependencies()
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен пользователем")
