from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from messages import (
    FAQ_TEXT,
    KEY_GENERATED_TEXT,
    PAID_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
)
from services import CheckFirstMonthFreeService, FirstMonthFreeService

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    if available_free_period != "NOT_AVAILABLE":
        boost_button = InlineKeyboardButton(
            text="🔥 Ускорить", callback_data="boost_free"
        )
    else:
        boost_button = InlineKeyboardButton(
            text="🔥 Ускорить", callback_data="boost_paid"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [boost_button],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
        ]
    )
    await message.answer(
        text=text,
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery):
    await callback.answer()

    response = await FirstMonthFreeService()(telegram_id=str(callback.message.chat.id))
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔥 Подключиться",
                url=response.url,
                callback_data=None,
            )
        ]
    ]
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(days=response.days),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery):
    keyboard = [
        [
            InlineKeyboardButton(
                text="💳 Оплатить (135 ⭐️ ~ 199 RUB)",
                url="https://t.me/tribute/app?startapp=prAc",
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.answer(
        text=PAID_TEXT,
        reply_markup=reply_markup,
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
    await callback.message.answer(text=FAQ_TEXT)
