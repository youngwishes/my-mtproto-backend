from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import CryptoPaymentIntentStatusEnum, PaymentKindEnum, PaymentProviderEnum
from apps.payments.models import CryptoPaymentIntent
from apps.payments.selectors import (
    activate_crypto_intent_from_provider,
    claim_crypto_intent_for_fulfillment,
    conditionally_transition_crypto_intent,
    create_crypto_intent,
    create_subscription_payment,
    expire_active_crypto_intent,
    fail_crypto_intent_creation,
    fail_stale_creating_crypto_intent,
    finalize_crypto_intent_fulfillment,
    get_creating_crypto_intent,
    get_crypto_intent_by_id,
    get_crypto_intent_by_provider_invoice_id,
    get_crypto_intent_for_notification,
    get_payment_by_identity,
    get_reusable_crypto_intent,
    get_unfinished_crypto_intents,
    get_unnotified_fulfilled_crypto_intents,
    mark_crypto_intent_provider_expired,
    mark_crypto_intent_retryable,
    mark_crypto_notification_sent,
    reserve_crypto_intent_or_read_winner,
)
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    CryptoPaymentIntentFactory,
    PaymentFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestCryptoSelectors(TestCase):
    def test_reusable_and_creating_lookups_exclude_expired_intents(self) -> None:
        user = SystemUserFactory()
        now = timezone.now()
        reusable = CryptoPaymentIntentFactory(
            initiator=user,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=now + timedelta(minutes=1),
        )
        expired = CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(),
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=now - timedelta(seconds=1),
        )
        creating = CryptoPaymentIntentFactory(initiator=SystemUserFactory())

        self.assertEqual(
            get_reusable_crypto_intent(
                initiator_id=user.pk,
                purchase_kind=PaymentKindEnum.SUBSCRIPTION,
                now=now,
            ),
            reusable,
        )
        self.assertIsNone(
            get_reusable_crypto_intent(
                initiator_id=expired.initiator_id,
                purchase_kind=expired.purchase_kind,
                now=now,
            )
        )
        self.assertEqual(
            get_creating_crypto_intent(
                initiator_id=creating.initiator_id,
                purchase_kind=creating.purchase_kind,
            ),
            creating,
        )

    def test_intent_reads_and_reconciliation_querysets(self) -> None:
        provider_intent = CryptoPaymentIntentFactory(
            provider_invoice_id=101,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
        )
        retryable = CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(),
            status=CryptoPaymentIntentStatusEnum.RETRYABLE,
        )
        fulfilled_user = SystemUserFactory()
        fulfilled_payment = PaymentFactory(
            user=fulfilled_user,
            provider=PaymentProviderEnum.CRYPTO_PAY,
            kind=PaymentKindEnum.SUBSCRIPTION,
        )
        AppleCashbackPurchaseFactory(
            payment=fulfilled_payment,
            identity_key=(
                f"crypto_pay:{fulfilled_payment.charge_id}:subscription"
            ),
        )
        fulfilled = CryptoPaymentIntentFactory(
            initiator=fulfilled_user,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=fulfilled_payment,
        )
        historical_user = SystemUserFactory()
        historical_payment = PaymentFactory(
            user=historical_user,
            provider=PaymentProviderEnum.CRYPTO_PAY,
            kind=PaymentKindEnum.SUBSCRIPTION,
        )
        AppleCashbackPurchaseFactory(
            payment=historical_payment,
            identity_key=(
                f"crypto_pay:{historical_payment.charge_id}:subscription"
            ),
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
        )
        CryptoPaymentIntentFactory(
            initiator=historical_user,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            payment=historical_payment,
        )
        CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(),
            status=CryptoPaymentIntentStatusEnum.PROCESSING,
        )

        self.assertEqual(
            get_crypto_intent_by_provider_invoice_id(provider_invoice_id=101),
            provider_intent,
        )
        self.assertEqual(get_crypto_intent_by_id(intent_id=provider_intent.pk), provider_intent)
        self.assertEqual(
            list(get_unfinished_crypto_intents(limit=10)), [provider_intent, retryable]
        )
        self.assertEqual(
            list(get_unnotified_fulfilled_crypto_intents(limit=10)), [fulfilled]
        )

    def test_transition_and_creation_selectors_apply_compare_and_set(self) -> None:
        user = SystemUserFactory()
        intent = create_crypto_intent(
            initiator_id=user.pk,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            product_code="mtproto_30d",
            rub_amount="99.00",
            public_id=uuid4(),
        )

        self.assertEqual(
            conditionally_transition_crypto_intent(
                intent_id=intent.pk,
                from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
                to_status=CryptoPaymentIntentStatusEnum.CREATE_FAILED,
                updates={"last_error_code": "provider_error"},
            ),
            1,
        )
        self.assertEqual(
            conditionally_transition_crypto_intent(
                intent_id=intent.pk,
                from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
                to_status=CryptoPaymentIntentStatusEnum.ACTIVE,
                updates={},
            ),
            0,
        )
        intent.refresh_from_db()
        self.assertEqual(intent.last_error_code, "provider_error")

    def test_claim_requires_unpaid_eligible_status(self) -> None:
        intent = CryptoPaymentIntentFactory(status=CryptoPaymentIntentStatusEnum.ACTIVE)
        now = timezone.now()

        self.assertEqual(
            claim_crypto_intent_for_fulfillment(intent_id=intent.pk, attempted_at=now), 1
        )
        self.assertEqual(
            claim_crypto_intent_for_fulfillment(intent_id=intent.pk, attempted_at=now), 0
        )
        paid_intent = CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(),
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            payment=PaymentFactory(),
        )
        self.assertEqual(
            claim_crypto_intent_for_fulfillment(intent_id=paid_intent.pk, attempted_at=now), 0
        )

    def test_finalize_links_only_processing_intent_once(self) -> None:
        intent = CryptoPaymentIntentFactory(status=CryptoPaymentIntentStatusEnum.PROCESSING)
        payment = PaymentFactory()
        now = timezone.now()

        self.assertEqual(
            finalize_crypto_intent_fulfillment(
                intent_id=intent.pk,
                payment_id=payment.pk,
                paid_at=now,
                fulfilled_at=now,
            ),
            1,
        )
        self.assertEqual(
            finalize_crypto_intent_fulfillment(
                intent_id=intent.pk,
                payment_id=payment.pk,
                paid_at=now,
                fulfilled_at=now,
            ),
            0,
        )
        intent.refresh_from_db()
        self.assertEqual(intent.payment_id, payment.pk)

    def test_terminal_and_notification_transitions_are_guarded(self) -> None:
        fulfilled = CryptoPaymentIntentFactory(status=CryptoPaymentIntentStatusEnum.FULFILLED)
        active = CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(), status=CryptoPaymentIntentStatusEnum.ACTIVE
        )
        expired = CryptoPaymentIntentFactory(
            initiator=SystemUserFactory(), status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED
        )
        now = timezone.now()

        self.assertEqual(mark_crypto_intent_retryable(intent_id=fulfilled.pk, error_code="retry"), 0)
        self.assertEqual(mark_crypto_intent_provider_expired(intent_id=active.pk), 1)
        self.assertEqual(mark_crypto_intent_provider_expired(intent_id=expired.pk), 1)
        for status in set(CryptoPaymentIntentStatusEnum) - {
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
        }:
            intent = CryptoPaymentIntentFactory(initiator=SystemUserFactory(), status=status)
            self.assertEqual(mark_crypto_intent_provider_expired(intent_id=intent.pk), 0)
            intent.refresh_from_db()
            self.assertEqual(intent.status, status)
        self.assertEqual(mark_crypto_notification_sent(intent_id=fulfilled.pk, sent_at=now), 1)
        self.assertEqual(mark_crypto_notification_sent(intent_id=fulfilled.pk, sent_at=now), 0)
        for status in set(CryptoPaymentIntentStatusEnum) - {
            CryptoPaymentIntentStatusEnum.FULFILLED
        }:
            intent = CryptoPaymentIntentFactory(initiator=SystemUserFactory(), status=status)
            self.assertEqual(mark_crypto_notification_sent(intent_id=intent.pk, sent_at=now), 0)
            intent.refresh_from_db()
            self.assertIsNone(intent.notification_sent_at)
        self.assertIsNone(get_crypto_intent_for_notification(intent_id=fulfilled.pk))

    def test_expire_reserve_fail_and_activate_create_lifecycle(self) -> None:
        user = SystemUserFactory()
        now = timezone.now()
        active = CryptoPaymentIntentFactory(
            initiator=user,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=now,
        )
        self.assertEqual(
            expire_active_crypto_intent(
                initiator_id=user.pk,
                purchase_kind=active.purchase_kind,
                now=now,
            ),
            1,
        )
        stale = CryptoPaymentIntentFactory(initiator=user)
        stale.created_at = now - timedelta(minutes=1)
        stale.save(update_fields=["created_at"])
        self.assertEqual(
            fail_stale_creating_crypto_intent(
                initiator_id=user.pk,
                purchase_kind=stale.purchase_kind,
                stale_before=now,
            ),
            1,
        )
        created_intent, reserved = reserve_crypto_intent_or_read_winner(
            initiator_id=user.pk,
            purchase_kind=stale.purchase_kind,
            product_code="mtproto_30d",
            rub_amount="99.00",
            public_id=uuid4(),
        )
        self.assertTrue(reserved)
        for status in (
            CryptoPaymentIntentStatusEnum.CREATING,
            CryptoPaymentIntentStatusEnum.ACTIVE,
        ):
            existing_winner = CryptoPaymentIntentFactory(initiator=SystemUserFactory(), status=status)
            intent, created = reserve_crypto_intent_or_read_winner(
                initiator_id=existing_winner.initiator_id, purchase_kind=existing_winner.purchase_kind,
                product_code="mtproto_30d", rub_amount="99.00", public_id=uuid4(),
            )
            self.assertEqual((intent, created), (existing_winner, False))
            self.assertEqual(CryptoPaymentIntent.objects.filter(initiator=existing_winner.initiator).count(), 1)
        invoice = SimpleNamespace(
            invoice_id=404,
            bot_invoice_url="https://t.me/CryptoBot?start=404",
            created_at=now,
            expiration_date=now + timedelta(minutes=30),
        )
        activated = activate_crypto_intent_from_provider(intent_id=created_intent.pk, invoice=invoice)
        self.assertEqual(activated.status, CryptoPaymentIntentStatusEnum.ACTIVE)
        self.assertEqual(activated.provider_invoice_id, 404)
        failing = CryptoPaymentIntentFactory(initiator=SystemUserFactory())
        self.assertEqual(
            fail_crypto_intent_creation(intent_id=failing.pk, error_code="timeout"), 1
        )

    def test_payment_identity_and_subscription_creation(self) -> None:
        user = SystemUserFactory()
        key = MTPRotoKeyFactory(user=user)
        payment = create_subscription_payment(
            user_id=user.pk,
            key_id=key.pk,
            charge_id="invoice-41",
            provider=PaymentProviderEnum.CRYPTO_PAY,
        )

        self.assertEqual(payment.kind, PaymentKindEnum.SUBSCRIPTION)
        self.assertEqual(payment.key_id, key.pk)
        self.assertEqual(
            get_payment_by_identity(
                provider=PaymentProviderEnum.CRYPTO_PAY,
                charge_id="invoice-41",
                kind=PaymentKindEnum.SUBSCRIPTION,
            ),
            payment,
        )
