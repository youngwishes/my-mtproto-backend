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
    MY_SERVERS_TEXT,
    REFERRAL_CABINET,
)
from services import (
    BuyProductService,
    CheckFirstMonthFreeService,
    FirstMonthFreeService,
    GetInvoiceDataService,
    GetMyServersService,
    GetStarsInvoiceDataService,
    GetReferralCabinetService,
    GetReferralLinkService,
    UpdateUserKeyService,
)

from src.bot import bot

router = Router()


def _build_main_menu_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=callback_data)],
            [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
        ],
    )
    return keyboard.adjust(1).as_markup()


def _build_my_servers_keyboard(servers) -> InlineKeyboardMarkup:
    keyboard = []
    for server in servers:
        keyboard.append([InlineKeyboardButton(text=server.location, url=server.proxy_link)])
    keyboard.append([InlineKeyboardButton(text="🔄 Перевыпустить ссылки", callback_data="update_link")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("start"))
async def cmd_start(message: Message):
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(message.from_user.id),
        telegram_username=str(getattr(message.from_user, "username", None)),
        invited_from_username=invited_from_username,
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    callback_data = "boost_free" if available_free_period != "NOT_AVAILABLE" else "boost_paid"
    await message.answer(
        text=text,
        reply_markup=_build_main_menu_keyboard(callback_data),
    )


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery):
    available_free_period = await CheckFirstMonthFreeService()(
        telegram_id=str(callback.message.chat.id),
        telegram_username=str(getattr(callback.message.from_user, "username", None)),
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    callback_data = "boost_free" if available_free_period != "NOT_AVAILABLE" else "boost_paid"
    await callback.message.edit_text(
        text=text,
        reply_markup=_build_main_menu_keyboard(callback_data),
    )


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery):
    await callback.answer()
    response = await FirstMonthFreeService()(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
    ])
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "my_servers")
async def process_my_servers(callback: CallbackQuery):
    await callback.answer()
    response = await GetMyServersService()(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=MY_SERVERS_TEXT.format(expired_date=response.expired_date),
        reply_markup=_build_my_servers_keyboard(response.servers),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
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


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery):
    await callback.answer()
    response = await GetReferralCabinetService()(
        telegram_id=str(callback.message.chat.id)
    )
    keyboard = []
    if response.active_referrals_count >= 5:
        keyboard.append(
            [InlineKeyboardButton(
                text="🎁 Получить бесплатную ссылку",
                callback_data="get-referral-link",
            )]
        )
    keyboard.append(
        [InlineKeyboardButton(
            text="🔗 Поделиться ссылкой",
            switch_inline_query=f"Привет! Переходи по моей реферальной ссылке: {response.referral_link}",
        )]
    )
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")])
    await callback.message.edit_text(
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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Мои серверы", callback_data="my_servers")],
    ])
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="💳 ЮKassa — 79 ₽", callback_data="pay_yukassa")],
            [InlineKeyboardButton(text="⭐ Telegram Stars — 60 ★", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ],
    )
    await callback.message.edit_text(
        text=(
            "💰 <b>Выберите способ оплаты</b>\n\n"
            "• 💳 <b>ЮKassa</b> — 79 ₽/месяц\n"
            "  Банковская карта, SberPay, ЮMoney\n\n"
            "• ⭐ <b>Telegram Stars</b> — 60 ★/месяц\n"
            "  Оплата прямо в Telegram\n"
        ),
        parse_mode="HTML",
        reply_markup=keyboard.adjust(1).as_markup(),
    )


@router.callback_query(F.data == "pay_yukassa")
async def process_pay_yukassa(callback: CallbackQuery):
    await callback.answer()
    response = await GetInvoiceDataService()()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **response.asdict(),
    )


@router.callback_query(F.data == "pay_stars")
async def process_pay_stars(callback: CallbackQuery):
    await callback.answer()
    response = await GetStarsInvoiceDataService()()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=response.title,
        description=response.description,
        start_parameter="payment_stars",
        payload="payment_stars",
        currency=response.currency,
        prices=response.prices,
        provider_token=response.provider_token,
    )


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery):
    await UpdateUserKeyService()(telegram_id=str(callback.message.chat.id))
    await callback.answer("✅ Ссылки обновлены!")
    response = await GetMyServersService()(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=MY_SERVERS_TEXT.format(expired_date=response.expired_date),
        reply_markup=_build_my_servers_keyboard(response.servers),
        parse_mode="HTML",
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    if message.successful_payment.currency == "XTR":
        charge_id = message.successful_payment.telegram_payment_charge_id
        provider = "stars"
    else:
        charge_id = message.successful_payment.provider_payment_charge_id
        provider = "yukassa"

    try:
        await BuyProductService()(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        await message.answer(
            "⚠️ Оплата получена, но произошла ошибка при выдаче ключа.\n"
            "Пожалуйста, обратитесь в поддержку: @mtproto_keys"
        )
