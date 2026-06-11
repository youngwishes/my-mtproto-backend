from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from domains.free_trial.client import get_free_trial_client
from domains.free_trial.enums import FreeAvailable
from domains.free_trial.messages import (
    FAQ_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    KEY_GENERATED_TEXT,
)

router = Router()


def _build_start_keyboard(available_free_period: str) -> InlineKeyboardMarkup:
    callback_data = (
        "boost_free"
        if available_free_period != FreeAvailable.NOT_AVAILABLE
        else "boost_paid"
    )
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=callback_data)],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
            [InlineKeyboardButton(text="🔄 Перевыпустить ссылку", callback_data="update_link")],
        ],
    )
    return keyboard.adjust(1).as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass

    client = get_free_trial_client()
    available_free_period = await client.check_eligibility(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
        invited_from_username=invited_from_username,
    )
    await message.answer(
        text=FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period),
        reply_markup=_build_start_keyboard(available_free_period),
    )


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery) -> None:
    client = get_free_trial_client()
    available_free_period = await client.check_eligibility(
        telegram_id=str(callback.message.chat.id),
        telegram_username=str(getattr(callback.message.from_user, "username", None)),
    )
    await callback.message.edit_text(
        text=FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period),
        reply_markup=_build_start_keyboard(available_free_period),
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_free_trial_client()
    response = await client.activate(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ]
    )
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        text=FAQ_TEXT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Договор-оферта",
                        url="https://drive.google.com/file/d/13GI1ZuKBm4nZkNxESOokGM6fTAAxaCs7/view?usp=sharing",
                    )
                ],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
            ]
        ),
    )
