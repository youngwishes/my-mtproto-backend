from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.tests.factories import PaymentFactory, ProductFactory


class TestProductModel(TestCase):
    def test_product_code_is_unique(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductFactory(code=ProductCodeEnum.MTPROTO_30D)


class TestPaymentModel(TestCase):
    def test_vpn_payment_identity_is_unique_per_provider_charge_and_kind(self) -> None:
        PaymentFactory(
            provider=PaymentProviderEnum.YUKASSA,
            charge_id="vpn-charge-id",
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentFactory(
                    provider=PaymentProviderEnum.YUKASSA,
                    charge_id="vpn-charge-id",
                    kind=PaymentKindEnum.VPN_SUBSCRIPTION,
                )

    def test_subscription_payment_identity_is_not_limited_by_vpn_constraint(self) -> None:
        for _ in range(2):
            PaymentFactory(
                provider=PaymentProviderEnum.YUKASSA,
                charge_id="subscription-charge-id",
                kind=PaymentKindEnum.SUBSCRIPTION,
            )
