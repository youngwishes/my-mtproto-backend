from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
)
from apps.payments.models import CryptoPaymentIntent
from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory


class TestCryptoPaymentIntentModel(TestCase):
    def test_only_one_creating_or_active_intent_per_initiator_and_kind(self) -> None:
        user = SystemUserFactory()
        cases = (
            (
                CryptoPaymentIntentStatusEnum.CREATING,
                CryptoPaymentIntentStatusEnum.ACTIVE,
                False,
            ),
            (
                CryptoPaymentIntentStatusEnum.ACTIVE,
                CryptoPaymentIntentStatusEnum.CREATING,
                False,
            ),
            (
                CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                CryptoPaymentIntentStatusEnum.CREATING,
                True,
            ),
            (
                CryptoPaymentIntentStatusEnum.CREATE_FAILED,
                CryptoPaymentIntentStatusEnum.CREATING,
                True,
            ),
            (
                CryptoPaymentIntentStatusEnum.FULFILLED,
                CryptoPaymentIntentStatusEnum.ACTIVE,
                True,
            ),
        )

        for existing_status, new_status, is_allowed in cases:
            with self.subTest(existing=existing_status, new=new_status):
                CryptoPaymentIntent.objects.all().delete()
                CryptoPaymentIntent.objects.create(
                    initiator=user,
                    purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                    product_code="mtproto_30d",
                    rub_amount="99.00",
                    status=existing_status,
                )
                if is_allowed:
                    CryptoPaymentIntent.objects.create(
                        initiator=user,
                        purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                        product_code="mtproto_30d",
                        rub_amount="99.00",
                        status=new_status,
                    )
                else:
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        CryptoPaymentIntent.objects.create(
                            initiator=user,
                            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                            product_code="mtproto_30d",
                            rub_amount="99.00",
                            status=new_status,
                        )

    def test_provider_invoice_id_is_unique_when_present(self) -> None:
        user = SystemUserFactory()
        kwargs = {
            "initiator": user,
            "purchase_kind": PaymentKindEnum.SUBSCRIPTION,
            "product_code": "mtproto_30d",
            "rub_amount": "99.00",
            "status": CryptoPaymentIntentStatusEnum.FULFILLED,
            "provider_invoice_id": 42,
        }
        CryptoPaymentIntent.objects.create(**kwargs)

        with self.assertRaises(IntegrityError), transaction.atomic():
            CryptoPaymentIntent.objects.create(**kwargs)


class TestPaymentModel(TestCase):
    def test_crypto_payment_identity_is_unique_for_all_three_kinds(self) -> None:
        for kind in PaymentKindEnum:
            with self.subTest(kind=kind):
                PaymentFactory(
                    provider=PaymentProviderEnum.CRYPTO_PAY,
                    charge_id=f"invoice-{kind}",
                    kind=kind,
                )
                with self.assertRaises(IntegrityError), transaction.atomic():
                    PaymentFactory(
                        provider=PaymentProviderEnum.CRYPTO_PAY,
                        charge_id=f"invoice-{kind}",
                        kind=kind,
                    )

    def test_legacy_subscription_duplicates_remain_allowed(self) -> None:
        for _ in range(2):
            PaymentFactory(
                provider=PaymentProviderEnum.STARS,
                charge_id="legacy-subscription-charge",
                kind=PaymentKindEnum.SUBSCRIPTION,
            )
