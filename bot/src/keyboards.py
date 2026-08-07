from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.messages import (
    CRYPTO_PAY_BUTTON,
    PRIVACY_URL,
    SITE_URL,
    SUPPORT_URL,
    TERMS_URL,
    VPN_SETUP_URL,
)

if TYPE_CHECKING:
    from src.domains.links import ServerItem

_ROOT_BACK = InlineKeyboardButton(
    text="🔙 Назад", callback_data="show_start_screen"
)
_MTPROXY_BACK = InlineKeyboardButton(
    text="🔙 Назад", callback_data="show_mtproxy_menu"
)
_VPN_BACK = InlineKeyboardButton(
    text="🔙 Назад", callback_data="show_vpn_menu"
)
_MY_SERVERS = InlineKeyboardButton(
    text="📡 Мои серверы", callback_data="my_servers", style="primary"
)
LEGAL_CONSENT_CALLBACK = "accept_legal_terms"


def legal_consent(
    invited_from_username: str | None,
) -> InlineKeyboardMarkup:
    callback_data = LEGAL_CONSENT_CALLBACK
    if invited_from_username is not None:
        callback_data = f"{callback_data}:{invited_from_username}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принимаю",
                    callback_data=callback_data,
                    style="success",
                )
            ]
        ]
    )


def product_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ MTProxy",
                    callback_data="show_mtproxy_menu",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔐 VPN",
                    callback_data="show_vpn_menu",
                    style="primary",
                )
            ],
        ]
    )


def vpn_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Купить VPN",
                    callback_data="vpn",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 Моя подписка",
                    callback_data="vpn_subscription",
                    style="primary",
                )
            ],
            [InlineKeyboardButton(text="📖 Как настроить", url=VPN_SETUP_URL)],
            [InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_URL)],
            [_ROOT_BACK],
        ]
    )


def vpn_subscription() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_VPN_BACK]])


def mtproxy_menu(boost_callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Ускорить Telegram", callback_data=boost_callback_data, style="success")],
            [_MY_SERVERS],
            [InlineKeyboardButton(text="🎁 Подарить подписку", callback_data="gift_certificate", style="primary")],
            [InlineKeyboardButton(text="🤝 Реферальный кабинет", callback_data="referral")],
            [InlineKeyboardButton(text="📋 Информация", callback_data="info")],
            [
                InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_URL),
                InlineKeyboardButton(text="🌐 Наш сайт", url=SITE_URL),
            ],
            [_ROOT_BACK],
        ]
    )


def key_generated() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_MY_SERVERS], [_MTPROXY_BACK]])


def my_servers(servers: list[ServerItem]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=server.location, url=server.proxy_link, style="success")]
        for server in servers
    ]
    keyboard.append([InlineKeyboardButton(text="🔄 Перевыпустить ссылки", callback_data="update_link", style="primary")])
    keyboard.append([_MTPROXY_BACK])
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
            [_MTPROXY_BACK],
        ]
    )


def payment_methods(
    *, payment_methods: tuple[str, ...]
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="⭐ Telegram Stars — 99 ★",
                    callback_data="pay_stars",
                    style="primary",
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [InlineKeyboardButton(text=CRYPTO_PAY_BUTTON, callback_data="pay_crypto")]
        )
    keyboard.append([_MTPROXY_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def vpn_payment_methods(
    *, stars_price: int, payment_methods: tuple[str, ...]
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⭐ Telegram Stars — {stars_price} ★",
                    callback_data="vpn_pay_stars",
                    style="primary",
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=CRYPTO_PAY_BUTTON,
                    callback_data="vpn_pay_crypto",
                )
            ]
        )
    keyboard.append([_VPN_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def gift_certificate_payment_methods(
    *, payment_methods: tuple[str, ...]
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="⭐ Telegram Stars — 99 ★",
                    callback_data="gift_stars",
                    style="primary",
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [InlineKeyboardButton(text=CRYPTO_PAY_BUTTON, callback_data="gift_crypto")]
        )
    keyboard.append([_MTPROXY_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
    keyboard.append([_MTPROXY_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def referral_reward() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_MY_SERVERS]])
