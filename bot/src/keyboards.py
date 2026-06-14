from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

if TYPE_CHECKING:
    from src.domains.links import ServerItem

_OFFER_URL = (
    "https://drive.google.com/file/d/13GI1ZuKBm4nZkNxESOokGM6fTAAxaCs7/view?usp=sharing"
)
_BACK = InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")
_MY_SERVERS = InlineKeyboardButton(
    text="📡 Мои серверы", callback_data="my_servers", style="primary"
)


def main_menu(boost_callback_data: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=boost_callback_data, style="success")],
            [_MY_SERVERS],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
        ],
    )
    return keyboard.adjust(1).as_markup()


def key_generated() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_MY_SERVERS], [_BACK]])


def my_servers(servers: list[ServerItem]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=server.location, url=server.proxy_link, style="success")]
        for server in servers
    ]
    keyboard.append([InlineKeyboardButton(text="🔄 Перевыпустить ссылки", callback_data="update_link", style="primary")])
    keyboard.append([_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👀 Договор-оферта", url=_OFFER_URL)],
            [_BACK],
        ]
    )


def payment_methods() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="💳 ЮKassa — 99 ₽", callback_data="pay_yukassa", style="primary")],
            [InlineKeyboardButton(text="⭐ Telegram Stars — 80 ★", callback_data="pay_stars", style="primary")],
            [_BACK],
        ],
    )
    return keyboard.adjust(1).as_markup()


def referral_cabinet(*, active_referrals_count: int, referral_link: str) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    if active_referrals_count >= 5:
        keyboard.append(
            [InlineKeyboardButton(text="🎁 Получить бесплатную ссылку", callback_data="get-referral-link", style="success")]
        )
    keyboard.append(
        [InlineKeyboardButton(
            text="🔗 Поделиться ссылкой",
            switch_inline_query=f"Привет! Переходи по моей реферальной ссылке: {referral_link}",
        )]
    )
    keyboard.append([_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def referral_reward() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_MY_SERVERS]])
