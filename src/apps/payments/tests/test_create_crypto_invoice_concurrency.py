from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import Mock

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from apps.payments.clients import CryptoPayClient
from apps.payments.enums import CryptoPaymentIntentStatusEnum, PaymentKindEnum, ProductCodeEnum
from apps.payments.exceptions import CryptoInvoiceCreationInProgress
from apps.payments.models import CryptoPaymentIntent
from apps.payments.services.create_crypto_invoice import CreateOrReuseCryptoInvoiceService
from apps.payments.services.dtos import CreateCryptoInvoiceIn, CryptoInvoiceDTO
from apps.payments.tests.factories import ProductFactory, make_crypto_invoice
from apps.users.tests.factories import SystemUserFactory


@override_settings(CRYPTOPAY_REQUEST_TIMEOUT=5.0)
class TestCreateCryptoInvoiceConcurrency(TransactionTestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.user = SystemUserFactory(username="1487189460")
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client = Mock(spec=CryptoPayClient)
        self.client.create_invoice.side_effect = self._create_invoice
        self.service = CreateOrReuseCryptoInvoiceService(
            crypto_pay_client=self.client,
            clock=lambda: self.now,
        )
        self.request = CreateCryptoInvoiceIn(
            username=self.user.username,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
        )
    def _create_invoice(
        self, *, amount: Decimal, payload: str, description: str
    ) -> CryptoInvoiceDTO:
        return make_crypto_invoice(
            status="active",
            paid_asset=None,
            paid_at=None,
            amount=amount,
            payload=payload,
            created_at=self.now,
            expiration_date=self.now + timedelta(seconds=1800),
        )
    def test_two_requests_leave_one_live_reservation(self) -> None:
        barrier = Barrier(2)

        def create() -> int:
            close_old_connections()
            barrier.wait()
            try:
                self.service(request=self.request)
            except CryptoInvoiceCreationInProgress:
                return 409
            finally:
                close_old_connections()
            return 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: create(), range(2)))
        self.assertIn(200, statuses)
        self.assertTrue(all(status in {200, 409} for status in statuses))
        self.assertEqual(
            CryptoPaymentIntent.objects.filter(
                initiator=self.user,
                purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                status__in=(
                    CryptoPaymentIntentStatusEnum.CREATING,
                    CryptoPaymentIntentStatusEnum.ACTIVE,
                ),
            ).count(),
            1,
        )
        self.assertEqual(self.client.create_invoice.call_count, 1)
