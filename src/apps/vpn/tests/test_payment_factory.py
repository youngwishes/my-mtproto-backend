from __future__ import annotations

import uuid
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import Payment
from apps.payments.tests.factories import PaymentReceiptFactory, ProductFactory
from apps.vpn.factories.payment_receipts import get_vpn_payment_receipt_service
from apps.vpn.models import VPNAccess, VPNPurchase


class VPNPaymentReceiptFactoryTest(TestCase):
    def test_vpn_owned_factory_injects_concrete_fulfillment_into_payment_owner(self) -> None:
        receipt = PaymentReceiptFactory(
            product=ProductFactory(code=ProductCodeEnum.VLESS_30D)
        )
        callbacks: list[object] = []
        scheduler = Mock()
        service = get_vpn_payment_receipt_service(
            schedule_delivery=scheduler,
            register_after_commit=callbacks.append,
            sleep=lambda _: None,
        )

        result = service(receipt_id=receipt.pk, lease_id=uuid.uuid4())

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(VPNAccess.objects.count(), 1)
        self.assertEqual(VPNPurchase.objects.count(), 1)
        receipt.refresh_from_db()
        self.assertEqual(receipt.payment_id, result.payment_id)
        scheduler.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        scheduler.assert_called_once_with(access_id=result.access_id)

    def test_factory_has_no_runnable_task_side_effect(self) -> None:
        scheduler = Mock()

        get_vpn_payment_receipt_service(schedule_delivery=scheduler)

        scheduler.assert_not_called()

    def test_purchase_failure_rolls_back_domain_writes_but_keeps_claim(self) -> None:
        receipt = PaymentReceiptFactory(
            product=ProductFactory(code=ProductCodeEnum.VLESS_30D)
        )
        lease_id = uuid.uuid4()
        with patch.object(
            VPNPurchase.objects,
            "create",
            side_effect=RuntimeError("purchase failed"),
        ):
            service = get_vpn_payment_receipt_service(
                schedule_delivery=Mock(),
                sleep=lambda _: None,
            )
            with self.assertRaisesRegex(RuntimeError, "purchase failed"):
                service(receipt_id=receipt.pk, lease_id=lease_id)

        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "processing")
        self.assertEqual(receipt.attempt_count, 1)
        self.assertEqual(receipt.lease_id, lease_id)
        self.assertIsNone(receipt.payment_id)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(VPNAccess.objects.exists())
