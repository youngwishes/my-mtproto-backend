from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.messages import PRIVACY_URL, SITE_URL, SUPPORT_URL, TERMS_URL

if TYPE_CHECKING:
    from src.domains.links import ServerItem

_BACK = InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")
_MY_SERVERS = InlineKeyboardButton(
    text="📡 Мои серверы", callback_data="my_servers", style="primary"
)


def main_menu(boost_callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=boost_callback_data, style="success")],
            [_MY_SERVERS],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [
                InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_URL),
                InlineKeyboardButton(text="🌐 Наш сайт", url=SITE_URL),
            ],
        ]
    )


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


def confirm_reissue() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, перевыпустить", callback_data="update_link_confirm", style="primary")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="my_servers")],
        ]
    )


def info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 Условия использования", url=TERMS_URL)],
            [InlineKeyboardButton(text="🔒 Политика конфиденциальности", url=PRIVACY_URL)],
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
