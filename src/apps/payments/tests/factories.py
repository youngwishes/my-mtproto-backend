from datetime import UTC, datetime, timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
    ProductCodeEnum,
)
from apps.payments.models import (
    AppleCashbackPurchase,
    AppleRedemption,
    CryptoPaymentIntent,
    GiftCertificate,
    Payment,
    PlategaPaymentIntent,
    Product,
)
from apps.payments.services.dtos.crypto_pay_dtos import CryptoInvoiceDTO


class ProductFactory(factory.django.DjangoModelFactory):
    code = factory.Sequence(lambda n: f"product_{n}")
    title = factory.Sequence(function=lambda n: f"title{n}")
    description = factory.Sequence(function=lambda n: f"description_{n}")
    price = 99
    stars_price = 99
    currency = "RUB"

    class Meta:
        model = Product


class PaymentFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    key = None
    charge_id = factory.Sequence(lambda n: f"charge_{n}")
    provider = PaymentProviderEnum.STARS

    class Meta:
        model = Payment


class AppleCashbackPurchaseFactory(factory.django.DjangoModelFactory):
    payment = factory.SubFactory(PaymentFactory)
    identity_key = factory.Sequence(lambda n: f"stars:cashback-{n}:subscription")
    rate_percent = 5
    apples_earned = 5
    balance_after = 5
    eligible_purchase_count_after = 1
    result_expired_at = None

    class Meta:
        model = AppleCashbackPurchase


class AppleRedemptionFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    key = factory.SubFactory("apps.vds.tests.factories.MTPRotoKeyFactory", user=factory.SelfAttribute("..user"))
    apples_spent = 15
    quoted_expired_at = factory.LazyFunction(timezone.now)
    new_expired_at = None
    balance_after = None

    class Meta:
        model = AppleRedemption


class CryptoPaymentIntentFactory(factory.django.DjangoModelFactory):
    initiator = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    purchase_kind = PaymentKindEnum.SUBSCRIPTION
    product_code = ProductCodeEnum.MTPROTO_30D
    rub_amount = Decimal("99.00")
    status = CryptoPaymentIntentStatusEnum.CREATING

    class Meta:
        model = CryptoPaymentIntent


class PlategaPaymentIntentFactory(factory.django.DjangoModelFactory):
    initiator = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    purchase_kind = PaymentKindEnum.SUBSCRIPTION
    product_code = ProductCodeEnum.MTPROTO_30D
    rub_amount = Decimal("99.00")
    status = PlategaPaymentIntentStatusEnum.CREATING

    class Meta:
        model = PlategaPaymentIntent


class GiftCertificateFactory(factory.django.DjangoModelFactory):
    code = factory.Sequence(lambda n: f"KEY-T{n:03d}-ABCD")
    buyer = factory.SubFactory("apps.users.tests.factories.SystemUserFactory")
    payment = factory.SubFactory(PaymentFactory)
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=365)
    )

    class Meta:
        model = GiftCertificate


def make_crypto_invoice(
    *,
    invoice_id: int = 731,
    status: str = "paid",
    currency_type: str = "fiat",
    fiat: str | None = "RUB",
    amount: Decimal = Decimal("99.00"),
    accepted_assets: frozenset[str] = frozenset({"USDT", "TON"}),
    paid_asset: str | None = "USDT",
    payload: str = "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
    bot_invoice_url: str = "https://t.me/CryptoBot?start=test",
    created_at: datetime = datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    expiration_date: datetime = datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
    paid_at: datetime | None = datetime(2026, 8, 2, 12, 20, tzinfo=UTC),
) -> CryptoInvoiceDTO:
    return CryptoInvoiceDTO(
        invoice_id=invoice_id,
        status=status,
        currency_type=currency_type,
        fiat=fiat,
        amount=amount,
        accepted_assets=accepted_assets,
        paid_asset=paid_asset,
        payload=payload,
        bot_invoice_url=bot_invoice_url,
        created_at=created_at,
        expiration_date=expiration_date,
        paid_at=paid_at,
    )
