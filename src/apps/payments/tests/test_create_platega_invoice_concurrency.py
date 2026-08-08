from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import Mock
from uuid import uuid4

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from apps.payments.clients import PlategaClient
from apps.payments.enums import PaymentKindEnum, PlategaPaymentIntentStatusEnum, ProductCodeEnum
from apps.payments.exceptions import PlategaInvoiceCreationInProgress
from apps.payments.models import PlategaPaymentIntent
from apps.payments.services.create_platega_invoice import CreateOrReusePlategaInvoiceService
from apps.payments.services.dtos import CreatePlategaInvoiceIn, PlategaTransactionDTO
from apps.payments.tests.factories import ProductFactory
from apps.users.tests.factories import SystemUserFactory


@override_settings(PLATEGA_REQUEST_TIMEOUT=5.0)
class TestCreatePlategaInvoiceConcurrency(TransactionTestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.user = SystemUserFactory(username="1487189460")
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client = Mock(spec=PlategaClient)
        self.client.create_transaction.side_effect = self._create_transaction
        self.service = CreateOrReusePlategaInvoiceService(
            platega_client=self.client,
            clock=lambda: self.now,
        )
        self.request = CreatePlategaInvoiceIn(
            username=self.user.username,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
        )

    def _create_transaction(self, **_: object) -> PlategaTransactionDTO:
        return PlategaTransactionDTO(
            transaction_id=uuid4(),
            status="PENDING",
            redirect_url="https://pay.example/transaction",
            expires_in=timedelta(minutes=15),
        )

    def test_two_concurrent_requests_create_one_provider_transaction_and_live_row(self) -> None:
        barrier = Barrier(2)

        def create() -> int:
            close_old_connections()
            barrier.wait()
            try:
                self.service(request=self.request)
            except PlategaInvoiceCreationInProgress:
                return 409
            finally:
                close_old_connections()
            return 200

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: create(), range(2)))
        self.assertIn(200, statuses)
        self.assertTrue(all(status in {200, 409} for status in statuses))
        self.assertEqual(
            PlategaPaymentIntent.objects.filter(
                initiator=self.user,
                purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                status__in=(
                    PlategaPaymentIntentStatusEnum.CREATING,
                    PlategaPaymentIntentStatusEnum.ACTIVE,
                ),
            ).count(),
            1,
        )
        self.assertEqual(self.client.create_transaction.call_count, 1)
