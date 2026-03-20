from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from messages import (
    FAQ_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    KEY_GENERATED_TEXT,
    KEY_UPDATED_TEXT,
    REFERRAL_CABINET,
)
from services import (
    BuyProductService,
    CheckFirstMonthFreeService,
    FirstMonthFreeService,
    GetInvoiceDataService,
    GetReferralCabinetService,
    GetReferralLinkService,
    UpdateUserKeyService,
)

from src.bot import bot

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
            [InlineKeyboardButton(text="🇳🇱 Ускорить", callback_data=callback_data)],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [
                InlineKeyboardButton(
                    text="⚡️ Реферальный кабинет", callback_data="referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔧️ Перевыпустить ссылку", callback_data="update_link"
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
                text="🇳🇱 Подключиться",
                url=response.link,
                callback_data=None,
            )
        ]
    ]
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        text=FAQ_TEXT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Договор-оферта",
                        url="https://drive.google.com/file/d/13GI1ZuKBm4nZkNxESOokGM6fTAAxaCs7/view?usp=sharing",
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery):
    await callback.answer()

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
    await callback.answer()

    response = await GetReferralLinkService()(telegram_id=str(callback.message.chat.id))
    keyboard = [
        [
            InlineKeyboardButton(
                text="🇳🇱 Подключиться",
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


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery):
    await callback.answer()

    response = await GetInvoiceDataService()()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **response.asdict(),
    )


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery):
    await callback.answer()

    response = await UpdateUserKeyService()(telegram_id=str(callback.message.chat.id))
    keyboard = [
        [
            InlineKeyboardButton(
                text="🇳🇱 Подключиться",
                url=response.link,
                callback_data=None,
            )
        ]
    ]
    await callback.message.answer(
        text=KEY_UPDATED_TEXT.format(
            expired_date=response.expired_date,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    await BuyProductService()(
        telegram_id=message.from_user.id,
        provider_payment_charge_id=getattr(
            message.successful_payment, "provider_payment_charge_id", None
        ),
    )
