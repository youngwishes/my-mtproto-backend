from __future__ import annotations

from typing import TYPE_CHECKING

from src.enums import FreeAvailable
from src.presentation import format_user_date

if TYPE_CHECKING:
    from src.domains.payments import (
        ApplePurchaseOutcome,
        AppleRedemptionPreview,
        AppleRedemptionResult,
        AppleStatus,
    )

SITE_URL = "https://mtprotokeys.com"
SUPPORT_URL = "https://t.me/mtprotokeys_support"
VPN_SETUP_URL = "https://mtprotokeys.com/vpn/"
TERMS_URL = "https://mtprotokeys.com/terms"
PRIVACY_URL = "https://mtprotokeys.com/privacy"


def render_apple_status(*, status: AppleStatus) -> str:
    progress = (
        "Максимальный уровень достигнут"
        if status.is_max_level
        else (
            "До следующего уровня: "
            f"<b>{status.purchases_to_next_level}</b>"
        )
    )
    return (
        "🍏 <b>Мои яблоки</b>\n\n"
        f"Баланс: <b>{status.balance} 🍏</b>\n"
        "Покупок MTProxy: "
        f"<b>{status.eligible_purchase_count}</b>\n"
        f"Уровень: <b>{status.level}</b>\n"
        f"Кэшбэк: <b>{status.rate_percent}%</b>\n"
        f"{progress}\n\n"
        "Курс: <b>15 🍏 = 1 день</b>"
    )


def render_apple_spend(*, balance: int, redeemable_days: int) -> str:
    return (
        "🍏 <b>Потратить яблоки</b>\n\n"
        f"Баланс: <b>{balance} 🍏</b>\n"
        f"Доступно дней: <b>{redeemable_days}</b>\n\n"
        "Выберите вариант продления:"
    )


def render_insufficient_apples(*, missing_apples: int) -> str:
    return (
        f"🍏 Для обмена не хватает <b>{missing_apples} 🍏</b>.\n"
        "Курс: <b>15 🍏 = 1 день</b>"
    )


APPLE_KEY_REQUIRED_TEXT = (
    "🍏 Яблоки можно потратить только на продление своего "
    "существующего MTProxy-ключа."
)


def render_apple_redemption_preview(*, preview: AppleRedemptionPreview) -> str:
    return (
        "🍏 <b>Подтверждение обмена</b>\n\n"
        f"Списать: <b>{preview.apples_spent} 🍏</b>\n"
        f"Добавить дней: <b>{preview.days}</b>\n"
        "Продление до: "
        f"<b>{format_user_date(preview.projected_expired_date)}</b>\n\n"
        "Подтвердить обмен?"
    )


def render_apple_redemption_result(*, result: AppleRedemptionResult) -> str:
    return (
        "✅ <b>Яблоки обменены</b>\n\n"
        f"Списано: <b>{result.apples_spent} 🍏</b>\n"
        f"Добавлено дней: <b>{result.days}</b>\n"
        f"Продление до: <b>{format_user_date(result.expired_date)}</b>\n"
        f"Баланс: <b>{result.balance} 🍏</b>"
    )


def render_apple_purchase_outcome(*, outcome: ApplePurchaseOutcome) -> str:
    lines = [
        "",
        "",
        "🍏 <b>Кэшбэк</b>",
        f"Начислено: <b>{outcome.apples_earned} 🍏</b>",
        f"Ставка: <b>{outcome.rate_percent}%</b>",
        f"Баланс: <b>{outcome.balance} 🍏</b>",
        f"Уровень: <b>{outcome.level}</b>",
    ]
    if outcome.level_up:
        lines.extend(
            (
                "",
                f"🎉 Новый уровень: <b>{outcome.level}</b>",
                "Кэшбэк следующей покупки: "
                f"<b>{outcome.next_purchase_rate_percent}%</b>",
            )
        )
    return "\n".join(lines)

PRODUCT_MENU_TEXT = (
    "👋 Добро пожаловать в MTProto Keys!\n\n"
    "MTProxy, VPN, бонусы и полезные ссылки — всё здесь.\n"
    "Выберите, что вас интересует:"
)

_WELCOME_BODY = """
<b>⚡️ MTProto Keys Bot</b>

🌐 Не один сервер, а целая <b>сеть</b>
🔁 Упал один — <b>всегда есть резерв</b>
🌍 Серверы в <b>разных странах</b>
📱 Одна ссылка на <b>3 устройства</b>

👇 Жми «Мои серверы» и подключайся!
"""

WELCOME_TEXT_MONTH = _WELCOME_BODY + "\nПервый месяц — бесплатно."

WELCOME_TEXT_WEEK = _WELCOME_BODY + "\nПервая неделя — бесплатно."

WELCOME_TEXT_TWO_WEEK = (
    _WELCOME_BODY + "\nВы пришли по приглашению — первые две недели бесплатно."
)

WELCOME_TEXT_NOT_FREE = _WELCOME_BODY

FREE_AVAILABLE_TEXT_MAPPING = {
    FreeAvailable.MONTH: WELCOME_TEXT_MONTH,
    FreeAvailable.WEEK: WELCOME_TEXT_WEEK,
    FreeAvailable.TWO_WEEK: WELCOME_TEXT_TWO_WEEK,
    FreeAvailable.NOT_AVAILABLE: WELCOME_TEXT_NOT_FREE,
}

LEGAL_CONSENT_TEXT = f"""
<b>Перед началом работы</b>

Чтобы пользоваться сервисом, подтвердите, что вы принимаете
<a href="{TERMS_URL}">Пользовательское соглашение</a> и даёте
<a href="{PRIVACY_URL}">согласие на обработку персональных данных</a>.
"""


KEY_GENERATED_TEXT = """
🎉 <b>Твой персональный ключ готов!</b>

📝 <b>Как активировать:</b>
1. Нажми «Мои серверы» ниже
2. Подключи <b>все серверы</b> в Telegram — при падении одного он автоматически переключится на другой

⏳ Действительно до: <b>{expired_date}</b>

<i>🤝 Подпишись на наш канал — там все новости: @mtproto_keys</i>
"""

MY_SERVERS_TEXT = """
📡 <b>Твои серверы</b>

Подключи все серверы в Telegram — при отказе одного Telegram автоматически переключится на другой.

⏳ Ключ действителен до: <b>{expired_date}</b>

<i>👇 Нажми на каждый сервер чтобы добавить его</i>
"""

REISSUE_CONFIRM_TEXT = """
🔄 <b>Перевыпуск ссылок</b>

Будут созданы новые ссылки, а <b>старые перестанут работать</b>.

После перевыпуска нужно:
1. Удалить старые прокси в настройках Telegram
2. Добавить новые из «Мои серверы»

⏳ Перевыпускать можно не чаще раза в 5 минут.

Продолжить?
"""

REISSUE_DONE_BANNER = """✅ <b>Ссылки перевыпущены!</b>

Старые больше не работают. В настройках Telegram удали старые прокси и добавь новые — кнопками ниже.
"""

FAQ_TEXT = """
❓ <b>Частые вопросы</b>

<b>Это безопасно для аккаунта?</b>
🔒 Да. Прокси не трогает твой аккаунт и пароль — Telegram поддерживает прокси штатно. Бан за это не грозит.

<b>Почему несколько серверов, а не один?</b>
🔁 Ты подключаешь все сразу. Если один сервер недоступен, Telegram молча переключается на следующий — связь не рвётся.

<b>Telegram тормозит или не грузит медиа?</b>
⚡️ Прокси помогает Telegram работать стабильнее и уменьшает потери при плохом интернете, защищает трафик. Максимальная скорость зависит от твоего интернета.

<b>На скольких устройствах работает?</b>
📱 Один ключ работает на трёх — например, телефон, ПК и планшет. А серверов несколько — добавь все и получишь запас.

<b>Нужно что-то устанавливать?</b>
🔧 Нет. Открываешь ссылку — ключ добавляется в настройки Telegram. Больше ничего.

<b>Есть бесплатный период?</b>
🎁 Да, новый пользователь получает бесплатный доступ — проверь, прежде чем платить.

<b>Период закончился — что дальше?</b>
🔄 Можно купить подписку — ключ продлится на 30 дней, переподключать ничего не нужно.

<b>Сколько стоит?</b>
⭐ 99 ★/мес через Telegram Stars.

Остались вопросы? Напиши @mtprotokeys_support
"""

REFERRAL_CABINET = """
<b>Реферальная программа</b>

• Общее количество инвайтов: <b>{total_referrals_count}</b>
• Активированные инвайты: <b>{active_referrals_count}</b>

🔗 Как только количество активированных инвайтов станет равно <b>5</b>, ты сможешь получить бесплатную ссылку <b>сроком действия 2 недели!</b>

👇 <b>Поделиться ссылкой</b>
"""

REFERRAL_REWARD_TEXT = """
🎁 <b>Ты получил 14 дней MTProxy!</b>

⏳ Действительно до: <b>{expired_date}</b>
"""

PAYMENT_METHODS_TEXT = f"""💳 <b>Оплата подписки</b>

⚡ <b>Продукт:</b> MTProxy
📅 <b>Период:</b> 30 дней

После оплаты новый ключ будет выдан автоматически. Если у вас уже есть активный ключ, подписка продлится на 30 дней.

<i>Оплачивая подписку, вы принимаете <a href="{TERMS_URL}">Условия использования</a> и <a href="{PRIVACY_URL}">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""

MTPROXY_PURCHASED_TEXT = """🎉 <b>Спасибо за покупку!</b>

⏳ Подписка активна до: <b>{expired_date}</b>

👇 Нажми «Мои серверы», чтобы подключиться ко всем серверам"""

CRYPTO_PAY_BUTTON = "💎 Crypto Pay"
CRYPTO_INVOICE_TEXT = (
    "💎 <b>Счёт Crypto Pay</b>\n\n"
    "Сумма: <b>{rub_amount} ₽</b>\n"
    "Действует до: <b>{expires_at}</b>\n\n"
    "Нажмите кнопку ниже, чтобы открыть CryptoBot."
)
CRYPTO_INVOICE_ERROR_TEXT = (
    "Не удалось создать счёт Crypto Pay. Попробуйте нажать кнопку ещё раз."
)
PLATEGA_INVOICE_TEXT = (
    "⚡ <b>Счёт СБП</b>\n\n"
    "Сумма: <b>{rub_amount} ₽</b>\n"
    "Срок действия счета: 15 минут\n\n"
    "Нажмите кнопку ниже, чтобы перейти к оплате.\n\n"
    "<i>Результат будет выдан автоматически после подтверждения платежа.</i>"
)
PLATEGA_INVOICE_ERROR_TEXT = (
    "Не удалось создать счёт СБП. Попробуйте нажать кнопку ещё раз."
)

GIFT_CERTIFICATE_TEXT = f"""💳 <b>Оплата подарка</b>

🎁 <b>Продукт:</b> сертификат MTProxy
📅 <b>Период:</b> 30 дней

После оплаты вы получите одноразовый код, который можно переслать другому человеку. Код создаст новый ключ или продлит действующий на 30 дней.

<i>Оплачивая сертификат, вы принимаете <a href="{TERMS_URL}">Условия использования</a> и <a href="{PRIVACY_URL}">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""

GIFT_CERTIFICATE_PURCHASED_TEXT = """🎁 <b>Подарочный сертификат готов</b>

Код: <code>{code}</code>

Перешли этот код другу или родственнику. Для активации достаточно отправить код в этот бот.
"""

GIFT_CERTIFICATE_ACTIVATED_TEXT = """✅ <b>Сертификат активирован</b>

Подписка действует до: <b>{expired_date}</b>

Нажми «Мои серверы», чтобы подключить прокси.
"""

VPN_PRODUCT_MENU_TEXT = """🔐 <b>VPN от MTProto Keys</b>

🌐 Защищённое подключение к интернету
📱 Работает на Android, iOS, Windows и macOS
🔗 Постоянная subscription-ссылка
⚙️ Подключение через приложение HAPP

👇 Выберите действие:"""

VPN_MENU_TEXT = f"""💳 <b>Оплата подписки</b>

🔐 <b>Продукт:</b> VPN
📅 <b>Период:</b> 30 дней

После оплаты VPN-подписка будет активирована автоматически. При продлении ваша постоянная subscription-ссылка не изменится.

<i>Оплачивая подписку, вы принимаете <a href="{TERMS_URL}">Условия использования</a> и <a href="{PRIVACY_URL}">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""

VPN_EXPIRED_TEXT = """🔐 <b>VPN-подписка закончилась</b>

Она действовала до: <b>{expired_at}</b>

Subscription-ссылка:
<code>{subscription_url}</code>"""

VPN_ACTIVE_TEXT = """🔐 <b>Твоя VPN-подписка активна</b>

Действует до: <b>{expired_at}</b>

Subscription-ссылка:
<code>{subscription_url}</code>"""

VPN_REISSUE_CONFIRM_TEXT = """🔄 <b>Перевыпуск VPN-ссылки</b>

Будет создана новая subscription-ссылка, а старая перестанет работать.
Продолжить?"""

VPN_REISSUE_DONE_BANNER = """✅ <b>VPN-ссылка перевыпущена!</b>

Старая subscription-ссылка больше не работает."""

VPN_PURCHASED_TEXT = """✅ <b>VPN-подписка активирована</b>

Действует до: <b>{expired_at}</b>

Твоя постоянная subscription-ссылка:
<code>{subscription_url}</code>

<b>Как подключить в HAPP</b>
1. Открой HAPP на Android, iOS, Windows или macOS.
2. Добавь subscription-ссылку и вставь ссылку выше.
3. Обнови подписку и подключись к подходящему профилю.
"""
