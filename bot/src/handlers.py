from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from messages import (
    FAQ_TEXT,
    KEY_GENERATED_TEXT,
    PAID_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    REFERRAL_CABINET,
)
from services import (
    CheckFirstMonthFreeService,
    FirstMonthFreeService,
    GetReferralCabinetService,
    GetReferralLinkService,
)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    try:
        invited_from_username = int(message.text.split()[-1])
        if invited_from_username == message.from_user.id:
            invited_from_username = ""
    except ValueError:
        invited_from_username = ""
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
        invited_from_username=str(invited_from_username),
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    if available_free_period != "NOT_AVAILABLE":
        callback_data = "boost_free"
    else:
        callback_data = "boost_paid"

    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="🔥 Ускорить", callback_data=callback_data)],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [
                InlineKeyboardButton(
                    text="⚡️ Реферальный кабинет", callback_data="referral"
                )
            ],
        ],
    )
    await message.answer(
        text=text,
        reply_markup=keyboard.adjust(2).as_markup(),
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery):
    await callback.answer()

    response = await FirstMonthFreeService()(telegram_id=str(callback.message.chat.id))
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔥 Подключиться",
                url=response.link,
                callback_data=None,
            )
        ]
    ]
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
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


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery):
    response = await GetReferralCabinetService()(
        telegram_id=str(callback.message.chat.id)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                text="🎁 Получить бесплатную ссылку",
                callback_data="get-referral-link",
            )
        ]
    ]
    await callback.message.answer(
        text=REFERRAL_CABINET.format(
            total_referrals_count=response.total_referrals_count,
            active_referrals_count=response.active_referrals_count,
            referral_link=response.referral_link,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "get-referral-link")
async def process_referral_link(callback: CallbackQuery):
    response = await GetReferralLinkService()(telegram_id=str(callback.message.chat.id))
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔥 Подключиться",
                url=response.link,
                callback_data=None,
            )
        ]
    ]
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(
            expired_date=response.expired_date,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
