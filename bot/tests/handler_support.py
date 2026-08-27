from __future__ import annotations

from aiogram.types import LabeledPrice
from src.domains.free_trial import FreeTrialKey
from src.domains.links import ReissuedKey
from src.domains.payments import (
    ActivatedGiftCertificate,
    ApplePurchaseOutcome,
    ConfirmedPurchase,
    GiftCertificate,
    StarsInvoice,
)
from src.domains.referrals import ReferralRewardKey
from src.domains.vpn import VPNMenu, VPNPurchase, VPNReissue
from src.exceptions import (
    APIError,
)

APPROVED_MTPROXY_PAYMENT_TEXT = """💳 <b>Оплата подписки</b>

⚡ <b>Продукт:</b> MTProxy
📅 <b>Период:</b> 30 дней

После оплаты новый ключ будет выдан автоматически. Если у тебя уже есть активный ключ, подписка продлится на 30 дней.

<i>Оплата подписки означает принятие <a href="https://mtprotokeys.com/terms">Условий использования</a> и <a href="https://mtprotokeys.com/privacy">Политики конфиденциальности</a>.</i>

👇 <b>Выбери способ оплаты:</b>"""


APPROVED_VPN_PAYMENT_TEXT = """💳 <b>Оплата подписки</b>

🔐 <b>Продукт:</b> VPN
📅 <b>Период:</b> 30 дней

После оплаты VPN-подписка будет активирована автоматически. При продлении твоя постоянная subscription-ссылка не изменится.

<i>Оплата подписки означает принятие <a href="https://mtprotokeys.com/terms">Условий использования</a> и <a href="https://mtprotokeys.com/privacy">Политики конфиденциальности</a>.</i>

👇 <b>Выбери способ оплаты:</b>"""


APPROVED_GIFT_PAYMENT_TEXT = """💳 <b>Оплата подарка</b>

🎁 <b>Продукт:</b> сертификат MTProxy
📅 <b>Период:</b> 30 дней

После оплаты ты получишь одноразовый код, который можно переслать другому человеку. Код создаст новый ключ или продлит действующий на 30 дней.

<i>Оплата сертификата означает принятие <a href="https://mtprotokeys.com/terms">Условий использования</a> и <a href="https://mtprotokeys.com/privacy">Политики конфиденциальности</a>.</i>

👇 <b>Выбери способ оплаты:</b>"""


def apple_loyalty(
    *,
    apples_earned: int = 5,
    rate_percent: int = 5,
    balance: int = 20,
    eligible_purchase_count: int = 4,
    level: str = "Садовник",
    level_up: bool = True,
    next_purchase_rate_percent: int = 10,
) -> ApplePurchaseOutcome:
    return ApplePurchaseOutcome(
        apples_earned=apples_earned,
        rate_percent=rate_percent,
        balance=balance,
        eligible_purchase_count=eligible_purchase_count,
        level=level,
        level_up=level_up,
        next_purchase_rate_percent=next_purchase_rate_percent,
    )


class FakeFreeTrial:
    def __init__(
        self,
        *,
        check="MONTH",
        key=None,
        consent=True,
        accept_result=True,
    ) -> None:
        self._check = check
        self._key = key or FreeTrialKey(expired_date="2026-07-14")
        self._consent = consent
        self._accept_result = accept_result
        self.checked: list[tuple] = []
        self.claimed: list[str] = []
        self.status_checked: list[str] = []
        self.accepted: list[tuple] = []

    async def get_consent_status(self, *, telegram_id):
        self.status_checked.append(telegram_id)
        return self._consent

    async def accept_consent(
        self, *, telegram_id, telegram_username, invited_from_username=None
    ):
        self.accepted.append((telegram_id, telegram_username, invited_from_username))
        return self._accept_result

    async def check_availability(
        self, *, telegram_id, telegram_username, invited_from_username=None
    ):
        self.checked.append((telegram_id, telegram_username, invited_from_username))
        return self._check

    async def claim(self, *, telegram_id):
        self.claimed.append(telegram_id)
        return self._key


class FakeLinks:
    def __init__(self, *, servers, reissue=None) -> None:
        self._servers = servers
        self._reissue = reissue or ReissuedKey(expired_date="2026-07-14")
        self.get_calls: list[str] = []
        self.reissue_calls: list[str] = []

    async def get_my_servers(self, *, telegram_id):
        self.get_calls.append(telegram_id)
        return self._servers

    async def reissue(self, *, telegram_id):
        self.reissue_calls.append(telegram_id)
        return self._reissue


class FakeReferrals:
    def __init__(self, *, cabinet, reward=None) -> None:
        self._cabinet = cabinet
        self._reward = reward or ReferralRewardKey(expired_date="2026-06-28")
        self.cabinet_calls: list[str] = []
        self.reward_calls: list[str] = []

    async def get_cabinet(self, *, telegram_id):
        self.cabinet_calls.append(telegram_id)
        return self._cabinet

    async def claim_reward(self, *, telegram_id):
        self.reward_calls.append(telegram_id)
        return self._reward


class FakePayments:
    def __init__(
        self,
        *,
        stars=None,
        purchase=None,
        gift=None,
        activation=None,
        confirm_error=None,
        activation_error=None,
        crypto=None,
        crypto_error=None,
        platega=None,
        platega_error=None,
        apple_status=None,
        apple_preview=None,
        apple_result=None,
        apple_preview_error=None,
        apple_confirm_error=None,
    ) -> None:
        self._stars = stars
        default_loyalty = ApplePurchaseOutcome(
            apples_earned=5,
            rate_percent=5,
            balance=5,
            eligible_purchase_count=1,
            level="Новичок",
            level_up=False,
            next_purchase_rate_percent=5,
        )
        self._purchase = purchase or ConfirmedPurchase(
            expired_date="2026-09-18",
            loyalty=default_loyalty,
        )
        self._gift = gift or GiftCertificate(
            code="KEY-ABCD-1234",
            loyalty=default_loyalty,
        )
        self._activation = activation or ActivatedGiftCertificate(
            expired_date="2026-08-08"
        )
        self._confirm_error = confirm_error
        self._activation_error = activation_error
        self._crypto = crypto
        self._crypto_error = crypto_error
        self._platega = platega
        self._platega_error = platega_error
        self._apple_status = apple_status
        self._apple_preview = apple_preview
        self._apple_result = apple_result
        self._apple_preview_error = apple_preview_error
        self._apple_confirm_error = apple_confirm_error
        self.confirmed: list[tuple] = []
        self.gift_confirmed: list[tuple] = []
        self.activated: list[tuple] = []
        self.stars_invoice_calls = 0
        self.vpn_stars_invoice_calls = 0
        self.crypto_calls: list[tuple] = []
        self.platega_calls: list[tuple] = []
        self.apple_status_calls: list[int] = []
        self.apple_preview_calls: list[tuple[int, str]] = []
        self.apple_confirm_calls: list[tuple[int, int]] = []

    async def get_stars_invoice(self):
        self.stars_invoice_calls += 1
        return self._stars

    async def get_vpn_stars_invoice(self):
        self.vpn_stars_invoice_calls += 1
        return self._stars

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error
        return self._purchase

    async def confirm_gift_certificate_purchase(
        self, *, telegram_id, charge_id, provider
    ):
        self.gift_confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error
        return self._gift

    async def activate_gift_certificate(self, *, telegram_id, code):
        self.activated.append((telegram_id, code))
        if self._activation_error is not None:
            raise self._activation_error
        return self._activation

    async def create_crypto_invoice(self, *, telegram_id, purchase_kind):
        self.crypto_calls.append((telegram_id, purchase_kind))
        if self._crypto_error is not None:
            raise self._crypto_error
        return self._crypto

    async def create_platega_invoice(self, *, telegram_id, purchase_kind):
        self.platega_calls.append((telegram_id, purchase_kind))
        if self._platega_error is not None:
            raise self._platega_error
        return self._platega

    async def get_apple_status(self, *, telegram_id):
        self.apple_status_calls.append(telegram_id)
        return self._apple_status

    async def preview_apple_redemption(self, *, telegram_id, mode):
        self.apple_preview_calls.append((telegram_id, mode))
        if self._apple_preview_error is not None:
            raise self._apple_preview_error
        return self._apple_preview

    async def confirm_apple_redemption(self, *, telegram_id, confirmation_id):
        self.apple_confirm_calls.append((telegram_id, confirmation_id))
        if self._apple_confirm_error is not None:
            raise self._apple_confirm_error
        return self._apple_result


class FakeVPN:
    def __init__(
        self,
        *,
        menu: VPNMenu | list[VPNMenu],
        purchase: VPNPurchase | None = None,
        reissue: VPNReissue | None = None,
        reissue_error: APIError | None = None,
    ) -> None:
        self._menus = menu if isinstance(menu, list) else [menu]
        self._purchase = purchase or VPNPurchase(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        )
        self._reissue = reissue or VPNReissue(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/reissued/",
        )
        self._reissue_error = reissue_error
        self.menu_calls: list[str] = []
        self.purchase_calls: list[tuple] = []
        self.reissue_calls: list[str] = []
        self.events: list[str] = []

    async def get_menu(self, *, telegram_id):
        self.menu_calls.append(telegram_id)
        self.events.append("menu")
        return self._menus.pop(0)

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.purchase_calls.append((telegram_id, charge_id, provider))
        return self._purchase

    async def reissue(self, *, telegram_id):
        self.reissue_calls.append(telegram_id)
        self.events.append("reissue")
        if self._reissue_error is not None:
            raise self._reissue_error
        return self._reissue


def _deps_with_vpn(*, vpn: FakeVPN, payments: FakePayments | None = None):
    from src.dependencies import Dependencies

    if payments is None:
        payments = FakePayments(
            stars=StarsInvoice(
                title="VPN на месяц",
                description="VPN-подписка",
                prices=[LabeledPrice(label="VPN на месяц", amount=149)],
                rub_amount="149.00",
                payment_methods=("stars", "crypto_pay"),
                priority_payment_methods=(),
            ),
        )
    return Dependencies(
        free_trial=None,
        links=None,
        referrals=None,
        payments=payments,
        vpn=vpn,
    )
