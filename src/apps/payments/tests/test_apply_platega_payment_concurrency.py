from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

from django.db import OperationalError, close_old_connections
from django.test import TransactionTestCase

from apps.payments.enums import (
    PaymentProviderEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.exceptions import PlategaPaymentRetryable
from apps.payments.models import Payment
from apps.payments.services import CreatePaymentService
from apps.payments.services.apply_platega_payment import ApplyPlategaPaymentService
from apps.payments.services.dtos import ValidatedPlategaPaymentDTO
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.services.gift_certificates import (
    get_create_gift_certificate_service,
)
from apps.payments.tests.factories import PlategaPaymentIntentFactory
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_on_commit_service
from apps.vpn.services.fulfill_vpn_purchase_service import (
    FulfillVPNPurchaseService,
)


class TestApplyPlategaPaymentConcurrency(TransactionTestCase):
    def test_two_concurrent_calls_create_one_product_payment_and_notification(self) -> None:
        now = datetime(2026, 8, 8, 12, 30, tzinfo=UTC)
        transaction_id = uuid4()
        intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=transaction_id,
        )
        enqueue = mock.Mock()
        service = ApplyPlategaPaymentService(
            create_payment_service=CreatePaymentService(
                extend_key_service=get_extend_key_service(),
                issue_key_service=get_issue_key_on_commit_service(),
            ),
            fulfill_vpn_purchase_service=FulfillVPNPurchaseService(
                schedule_profiles=mock.Mock(),
                subscription_base_url="https://vpn.example",
            ),
            create_gift_certificate_service=get_create_gift_certificate_service(),
            enqueue_notification=enqueue,
            clock=lambda: now,
        )
        validated = ValidatedPlategaPaymentDTO(
            intent_id=intent.pk,
            transaction_id=transaction_id,
        )

        def apply() -> str:
            close_old_connections()
            try:
                result = service(payment=validated)
            except (PlategaPaymentRetryable, OperationalError):
                return "retry"
            finally:
                close_old_connections()
            return "fulfilled" if result.fulfilled else "duplicate"

        with mock.patch(
            "apps.vds.services.issue_key_service.push_key_to_servers_task"
        ), ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: apply(), range(2)))

        self.assertIn("fulfilled", outcomes)
        self.assertEqual(
            Payment.objects.filter(
                provider=PaymentProviderEnum.PLATEGA,
                charge_id=str(transaction_id),
            ).count(),
            1,
        )
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(enqueue.call_count, 1)
