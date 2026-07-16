from __future__ import annotations

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum, ProductCodeEnum
from apps.payments.models import PaymentReceipt
from apps.payments.selectors import (
    get_active_product_by_code,
    get_payment_intent_by_payload,
    get_payment_by_identity,
    get_payment_receipt_by_identity,
    get_recoverable_payment_receipts,
)
from apps.payments.tests.factories import (
    PaymentFactory,
    PaymentIntentFactory,
    PaymentReceiptFactory,
    ProductFactory,
)


class ProductSelectorsTest(TestCase):
    def test_returns_only_active_product_with_exact_stable_code(self) -> None:
        expected = ProductFactory(code=ProductCodeEnum.MTPROTO_30D)
        ProductFactory(code=ProductCodeEnum.VLESS_30D, is_active=False)

        result = get_active_product_by_code(code=ProductCodeEnum.MTPROTO_30D)

        self.assertEqual(result, expected)

    def test_does_not_fall_back_to_another_product(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D)

        result = get_active_product_by_code(code=ProductCodeEnum.VLESS_30D)

        self.assertIsNone(result)


class PaymentIntentSelectorsTest(TestCase):
    def test_returns_intent_by_exact_payload(self) -> None:
        expected = PaymentIntentFactory()

        result = get_payment_intent_by_payload(
            invoice_payload=expected.invoice_payload,
        )

        self.assertEqual(result, expected)


class PaymentReceiptSelectorsTest(TestCase):
    def test_returns_receipt_by_exact_provider_identity(self) -> None:
        expected = PaymentReceiptFactory()

        result = get_payment_receipt_by_identity(
            provider=expected.provider,
            charge_id=expected.charge_id,
        )

        self.assertEqual(result, expected)

    def test_exposes_legacy_payment_identity_collision(self) -> None:
        payment = PaymentFactory()

        result = get_payment_by_identity(
            provider=payment.provider,
            charge_id=payment.charge_id,
        )

        self.assertEqual(result, payment)

    def test_recovery_includes_received_due_retry_and_stale_processing(self) -> None:
        now = timezone.now()
        received = PaymentReceiptFactory(status=PaymentReceiptStatusEnum.RECEIVED)
        retry = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at=now,
        )
        stale = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.PROCESSING,
            processing_started_at=now - timedelta(minutes=6),
            lease_id=uuid.uuid4(),
        )
        PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at=now + timedelta(minutes=1),
        )
        PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.PROCESSING,
            processing_started_at=now - timedelta(minutes=4),
            lease_id=uuid.uuid4(),
        )
        applied = PaymentReceiptFactory()
        applied_payment = PaymentFactory(
            user=applied.user,
            product=applied.product,
            provider=applied.provider,
            charge_id=applied.charge_id,
        )
        applied_lease = uuid.uuid4()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=applied.pk,
            lease_id=applied_lease,
            started_at=now,
        )
        PaymentReceipt.objects.mark_applied(
            receipt_id=applied.pk,
            lease_id=applied_lease,
            payment=applied_payment,
        )

        result = list(
            get_recoverable_payment_receipts(
                due_at=now,
                stale_before=now - timedelta(minutes=5),
            )
        )

        self.assertCountEqual(result, [received, retry, stale])
