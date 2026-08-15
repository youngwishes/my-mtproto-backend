from __future__ import annotations

from decimal import Decimal
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
    text="🔙 Главное меню", callback_data="show_start_screen"
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
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔐 VPN",
                    callback_data="show_vpn_menu",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤝 Реферальная программа",
                    callback_data="referral",
                )
            ],
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="🌐 Наш сайт", url=SITE_URL)],
            [
                InlineKeyboardButton(text="📜 Условия пользования", url=TERMS_URL),
                InlineKeyboardButton(
                    text="🔒 Политика конфиденциальности",
                    url=PRIVACY_URL,
                ),
            ],
        ]
    )


def vpn_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Купить или продлить VPN",
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
            [
                InlineKeyboardButton(
                    text="📖 Как подключить VPN",
                    url=VPN_SETUP_URL,
                )
            ],
            [_ROOT_BACK],
        ]
    )


def vpn_subscription(*, is_expired: bool) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    if is_expired:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="💳 Продлить VPN",
                    callback_data="vpn",
                    style="success",
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔄 Перевыпустить ссылку",
                callback_data="vpn_reissue",
                style="primary",
            )
        ]
    )
    if is_expired:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🔙 Назад в VPN",
                    callback_data="show_vpn_menu",
                )
            ]
        )
    else:
        keyboard.append([_VPN_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def vpn_reissue_confirmation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, перевыпустить",
                    callback_data="vpn_reissue_confirm",
                    style="primary",
                )
            ],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="vpn_subscription")],
        ]
    )


def vpn_purchased() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 Моя подписка",
                    callback_data="vpn_subscription",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад в VPN",
                    callback_data="show_vpn_menu",
                )
            ],
        ]
    )


def mtproxy_menu(boost_callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ Ускорить Telegram",
                    callback_data=boost_callback_data,
                    style="success",
                )
            ],
            [_MY_SERVERS],
            [
                InlineKeyboardButton(
                    text="🎁 Подарить MTProxy",
                    callback_data="gift_certificate",
                )
            ],
            [InlineKeyboardButton(text="❓ Вопросы о MTProxy", callback_data="info")],
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
    return InlineKeyboardMarkup(inline_keyboard=[[_MTPROXY_BACK]])


def payment_methods(
    *,
    stars_price: int,
    rub_amount: str,
    payment_methods: tuple[str, ...],
    priority_payment_methods: tuple[str, ...],
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    priority = set(priority_payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "platega_sbp" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⚡ СБП — {_format_rub_amount(rub_amount)} ₽",
                    callback_data="pay_platega_sbp",
                    style="primary" if "platega_sbp" in priority else None,
                )
            ]
        )
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⭐ Telegram Stars — {stars_price} ★",
                    callback_data="pay_stars",
                    style="primary" if "stars" in priority else None,
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=CRYPTO_PAY_BUTTON,
                    callback_data="pay_crypto",
                    style="primary" if "crypto_pay" in priority else None,
                )
            ]
        )
    keyboard.append([_MTPROXY_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def vpn_payment_methods(
    *,
    stars_price: int,
    rub_amount: str,
    payment_methods: tuple[str, ...],
    priority_payment_methods: tuple[str, ...],
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    priority = set(priority_payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "platega_sbp" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⚡ СБП — {_format_rub_amount(rub_amount)} ₽",
                    callback_data="vpn_pay_platega_sbp",
                    style="primary" if "platega_sbp" in priority else None,
                )
            ]
        )
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⭐ Telegram Stars — {stars_price} ★",
                    callback_data="vpn_pay_stars",
                    style="primary" if "stars" in priority else None,
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=CRYPTO_PAY_BUTTON,
                    callback_data="vpn_pay_crypto",
                    style="primary" if "crypto_pay" in priority else None,
                )
            ]
        )
    keyboard.append([_VPN_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def gift_certificate_payment_methods(
    *,
    stars_price: int,
    rub_amount: str,
    payment_methods: tuple[str, ...],
    priority_payment_methods: tuple[str, ...],
) -> InlineKeyboardMarkup:
    active = set(payment_methods)
    priority = set(priority_payment_methods)
    keyboard: list[list[InlineKeyboardButton]] = []
    if "platega_sbp" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⚡ СБП — {_format_rub_amount(rub_amount)} ₽",
                    callback_data="gift_platega_sbp",
                    style="primary" if "platega_sbp" in priority else None,
                )
            ]
        )
    if "stars" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⭐ Telegram Stars — {stars_price} ★",
                    callback_data="gift_stars",
                    style="primary" if "stars" in priority else None,
                )
            ]
        )
    if "crypto_pay" in active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=CRYPTO_PAY_BUTTON,
                    callback_data="gift_crypto",
                    style="primary" if "crypto_pay" in priority else None,
                )
            ]
        )
    keyboard.append([_MTPROXY_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def referral_cabinet(
    *,
    active_referrals_count: int,
    referral_link: str,
) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    if active_referrals_count >= 5:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🎁 Получить 14 дней MTProxy",
                    callback_data="get-referral-link",
                    style="success",
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔗 Поделиться ссылкой",
                switch_inline_query=(
                    "Привет! Переходи по моей реферальной ссылке: "
                    f"{referral_link}"
                ),
                style="primary",
            )
        ]
    )
    keyboard.append([_ROOT_BACK])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def referral_reward() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ Перейти в MTProxy",
                    callback_data="show_mtproxy_menu",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Реферальная программа",
                    callback_data="referral",
                )
            ],
        ]
    )


def _format_rub_amount(rub_amount: str) -> str:
    amount = Decimal(rub_amount).quantize(Decimal("0.01"))
    if amount == amount.to_integral_value():
        return format(amount, ".0f")
    return format(amount, ".2f").replace(".", ",")
