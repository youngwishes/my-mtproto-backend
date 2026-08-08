from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase

from apps.payments.enums import PaymentKindEnum, PlategaPaymentIntentStatusEnum
from apps.payments.selectors import (
    activate_platega_intent_from_provider,
    expire_active_platega_intent,
    fail_stale_creating_platega_intent,
    get_reusable_platega_intent,
    reserve_platega_intent_or_read_winner,
)
from apps.payments.services.dtos import PlategaTransactionDTO
from apps.payments.tests.factories import PlategaPaymentIntentFactory


class TestPlategaSelectors(TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=self.now + timedelta(minutes=15),
            provider_payment_url="https://pay.example/transaction",
        )

    def test_reuses_only_unexpired_active_intent(self) -> None:
        self.assertEqual(
            get_reusable_platega_intent(
                initiator_id=self.intent.initiator_id,
                purchase_kind=self.intent.purchase_kind,
                now=self.now,
            ).pk,
            self.intent.pk,
        )
        self.intent.provider_expires_at = self.now
        self.intent.save(update_fields=["provider_expires_at"])
        self.assertIsNone(
            get_reusable_platega_intent(
                initiator_id=self.intent.initiator_id,
                purchase_kind=self.intent.purchase_kind,
                now=self.now,
            )
        )

    def test_expires_stale_lease_reserves_and_activates_one_intent(self) -> None:
        self.intent.provider_expires_at = self.now
        self.intent.save(update_fields=["provider_expires_at"])
        self.assertEqual(
            expire_active_platega_intent(
                initiator_id=self.intent.initiator_id,
                purchase_kind=self.intent.purchase_kind,
                now=self.now,
            ),
            1,
        )
        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED)

        stale = PlategaPaymentIntentFactory(
            initiator=self.intent.initiator,
            purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )
        stale_at = self.now - timedelta(seconds=10)
        type(stale).objects.filter(pk=stale.pk).update(created_at=stale_at)
        self.assertEqual(
            fail_stale_creating_platega_intent(
                initiator_id=stale.initiator_id,
                purchase_kind=stale.purchase_kind,
                stale_before=stale_at,
            ),
            1,
        )

        reserved, created = reserve_platega_intent_or_read_winner(
            initiator_id=self.intent.initiator_id,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            product_code="mtproto_30d",
            rub_amount=Decimal("149.00"),
            public_id=uuid4(),
        )
        self.assertTrue(created)
        activated = activate_platega_intent_from_provider(
            intent_id=reserved.pk,
            transaction=PlategaTransactionDTO(
                transaction_id=uuid4(),
                status="PENDING",
                redirect_url="https://pay.example/transaction-new",
                expires_in=timedelta(minutes=15),
            ),
            expires_at=self.now + timedelta(minutes=15),
        )
        self.assertEqual(activated.status, PlategaPaymentIntentStatusEnum.ACTIVE)
        self.assertEqual(activated.rub_amount, Decimal("149.00"))
