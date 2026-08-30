from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.messages import (
    CHANNEL_URL,
    CRYPTO_PAY_BUTTON,
    PRIVACY_URL,
    SUPPORT_URL,
    TERMS_URL,
    VPN_SETUP_URL,
)
from src.presentation import format_rub_amount

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
DISMISS_ERROR_NOTIFICATION_CALLBACK = "dismiss_error_notification"


def reissue_error_notification() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧹 Понятно",
                    callback_data=DISMISS_ERROR_NOTIFICATION_CALLBACK,
                )
            ]
        ]
    )


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
            [InlineKeyboardButton(text="📣 Наш канал", url=CHANNEL_URL)],
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
                    text="🍏 Мои яблоки",
                    callback_data="apples_status",
                )
            ],
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


def apples_status(*, fortune_wheel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎡 Колесо фортуны",
                    web_app=WebAppInfo(url=fortune_wheel_url),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🍏 Потратить яблоки",
                    callback_data="apples_spend",
                    style="success",
                )
            ],
            [_MTPROXY_BACK],
        ]
    )


def apples_spend() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Обменять на 1 день — 15 🍏",
                    callback_data="apples_redeem_one",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Обменять все яблоки",
                    callback_data="apples_redeem_all",
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="apples_status")],
        ]
    )


def apples_back_to_status() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="apples_status")]
        ]
    )


def apples_redemption_confirmation(*, confirmation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"apples_confirm:{confirmation_id}",
                    style="success",
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="apples_spend")],
        ]
    )


def apples_redemption_done() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍏 Мои яблоки",
                    callback_data="apples_status",
                )
            ],
            [_MTPROXY_BACK],
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
                    text=f"⚡ СБП — {format_rub_amount(rub_amount)} ₽",
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
                    text=f"⚡ СБП — {format_rub_amount(rub_amount)} ₽",
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
                    text=f"⚡ СБП — {format_rub_amount(rub_amount)} ₽",
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
    referral_link: str,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="🍏 Потратить яблоки",
                callback_data="apples_spend",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Поделиться ссылкой",
                switch_inline_query=(
                    "Привет! Переходи по моей реферальной ссылке: "
                    f"{referral_link}"
                ),
                style="primary",
            )
        ],
        [_ROOT_BACK],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
