from __future__ import annotations

import ast
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

from django.db import OperationalError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum, ProductCodeEnum
from apps.payments.exceptions import (
    PaymentReceiptDatabaseBusy,
    PaymentReceiptLeaseUnavailable,
    PaymentReceiptTransactionBoundaryViolation,
)
from apps.payments.models import Payment, PaymentReceipt
from apps.payments.services.apply_payment_receipt import (
    ApplyPaymentReceiptService,
    _is_sqlite_lock_contention,
    get_apply_payment_receipt_service,
)
from apps.payments.services.dtos import (
    VPNPaymentFulfillmentIn,
    VPNPaymentFulfillmentOut,
)
from apps.payments.tests.factories import PaymentReceiptFactory, ProductFactory


class ApplyPaymentReceiptServiceTest(TestCase):
    def setUp(self) -> None:
        self.now = timezone.now()
        self.receipt = PaymentReceiptFactory(
            product=ProductFactory(code=ProductCodeEnum.VLESS_30D),
        )
        self.lease_id = uuid.uuid4()
        self.fulfill = Mock(
            return_value=VPNPaymentFulfillmentOut(
                access_id=11,
                purchase_id=12,
                is_ready=True,
            )
        )
        self.service = get_apply_payment_receipt_service(
            fulfill_purchase=self.fulfill,
            now=lambda: self.now,
            sleep=lambda _: None,
        )

    def test_claims_receipt_creates_payment_fulfills_and_marks_applied(self) -> None:
        result = self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        payment = Payment.objects.get(pk=result.payment_id)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.APPLIED)
        self.assertEqual(self.receipt.applied_at, self.now)
        self.assertEqual(self.receipt.ready_at, self.now)
        self.assertEqual(self.receipt.payment, payment)
        self.assertEqual(payment.user, self.receipt.user)
        self.assertEqual(payment.product, self.receipt.product)
        self.assertEqual(payment.provider, self.receipt.provider)
        self.assertEqual(payment.charge_id, self.receipt.charge_id)
        self.assertIsNone(payment.key)
        self.fulfill.assert_called_once_with(
            purchase=VPNPaymentFulfillmentIn(
                receipt_id=self.receipt.pk,
                payment_id=payment.pk,
                user_id=self.receipt.user_id,
                accepted_at=self.receipt.accepted_at,
            )
        )
        self.assertEqual(result.access_id, 11)
        self.assertEqual(result.purchase_id, 12)
        self.assertFalse(result.is_replay)

    def test_preparing_fulfillment_leaves_receipt_readiness_pending(self) -> None:
        self.fulfill.return_value = VPNPaymentFulfillmentOut(
            access_id=11,
            purchase_id=12,
            is_ready=False,
        )

        self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.applied_at, self.now)
        self.assertIsNone(self.receipt.ready_at)

    def test_applied_receipt_is_an_exact_replay_without_second_charge(self) -> None:
        first = self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        result = self.service(receipt_id=self.receipt.pk, lease_id=uuid.uuid4())

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(result.payment_id, first.payment_id)
        self.assertTrue(result.is_replay)
        self.assertEqual(self.fulfill.call_count, 1)

    def test_duplicate_or_stale_processing_lease_cannot_apply(self) -> None:
        current_lease = uuid.uuid4()
        PaymentReceipt.objects.claim_for_processing(
            receipt_id=self.receipt.pk,
            lease_id=current_lease,
            started_at=self.now - timedelta(hours=1),
        )

        for rejected_lease in (current_lease, uuid.uuid4()):
            with self.subTest(rejected_lease=rejected_lease):
                with self.assertRaises(PaymentReceiptLeaseUnavailable):
                    self.service(
                        receipt_id=self.receipt.pk,
                        lease_id=rejected_lease,
                    )

        self.assertFalse(Payment.objects.exists())
        self.fulfill.assert_not_called()

    def test_claim_refuses_outer_transaction_with_bounded_domain_error(self) -> None:
        with transaction.atomic():
            with (
                self.assertNumQueries(0),
                self.assertRaises(PaymentReceiptTransactionBoundaryViolation),
            ):
                self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.RECEIVED)
        self.assertEqual(self.receipt.attempt_count, 0)
        self.assertFalse(Payment.objects.exists())

    def test_wrong_lease_at_completion_rolls_back_payment_and_fulfillment(self) -> None:
        def invalidate_lease(**_: object) -> VPNPaymentFulfillmentOut:
            PaymentReceipt.objects.filter(pk=self.receipt.pk)._safe_update(
                lease_id=uuid.uuid4()
            )
            return VPNPaymentFulfillmentOut(
                access_id=11,
                purchase_id=12,
                is_ready=False,
            )

        service = get_apply_payment_receipt_service(
            fulfill_purchase=invalidate_lease,
            now=lambda: self.now,
            sleep=lambda _: None,
        )

        with self.assertRaises(PaymentReceiptLeaseUnavailable):
            service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.PROCESSING)
        self.assertEqual(self.receipt.lease_id, self.lease_id)
        self.assertFalse(Payment.objects.exists())

    def test_fulfillment_failure_rolls_back_domain_writes_but_keeps_claim(self) -> None:
        product_count = ProductFactory._meta.model.objects.count()

        def fail_after_domain_write(**_: object) -> None:
            ProductFactory()
            raise RuntimeError("purchase failed")

        self.fulfill.side_effect = fail_after_domain_write

        with self.assertRaisesRegex(RuntimeError, "purchase failed"):
            self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.PROCESSING)
        self.assertEqual(self.receipt.lease_id, self.lease_id)
        self.assertEqual(self.receipt.processing_started_at, self.now)
        self.assertEqual(self.receipt.attempt_count, 1)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(ProductFactory._meta.model.objects.count(), product_count)

    def test_due_retry_applies_once_after_failed_attempt(self) -> None:
        self.fulfill.side_effect = RuntimeError("temporary")
        with self.assertRaises(RuntimeError):
            self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)
        PaymentReceipt.objects.mark_for_retry(
            receipt_id=self.receipt.pk,
            lease_id=self.lease_id,
            next_attempt_at=self.now,
            error_code="unexpected_apply_error",
        )
        successful_fulfillment = Mock(
            return_value=VPNPaymentFulfillmentOut(
                access_id=21,
                purchase_id=22,
                is_ready=True,
            )
        )
        retry_service = get_apply_payment_receipt_service(
            fulfill_purchase=successful_fulfillment,
            now=lambda: self.now,
            sleep=lambda _: None,
        )

        result = retry_service(
            receipt_id=self.receipt.pk,
            lease_id=uuid.uuid4(),
        )
        replay = retry_service(
            receipt_id=self.receipt.pk,
            lease_id=uuid.uuid4(),
        )

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, PaymentReceiptStatusEnum.APPLIED)
        self.assertEqual(self.receipt.attempt_count, 2)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertFalse(result.is_replay)
        self.assertTrue(replay.is_replay)
        successful_fulfillment.assert_called_once()

    def test_two_distinct_charges_are_applied_in_accepted_order(self) -> None:
        second = PaymentReceiptFactory(
            user=self.receipt.user,
            product=self.receipt.product,
            accepted_at=self.receipt.accepted_at + timedelta(seconds=1),
        )

        self.service(receipt_id=self.receipt.pk, lease_id=self.lease_id)
        self.service(receipt_id=second.pk, lease_id=uuid.uuid4())

        self.assertEqual(
            [call.kwargs["purchase"].receipt_id for call in self.fulfill.call_args_list],
            [self.receipt.pk, second.pk],
        )
        self.assertEqual(Payment.objects.count(), 2)

    def test_retries_bounded_sqlite_lock_then_succeeds(self) -> None:
        real_claim = PaymentReceipt.objects.claim_for_processing
        attempts = 0

        def claim_after_two_locks(**kwargs: object) -> bool:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise OperationalError("database is locked")
            return real_claim(**kwargs)

        claim = Mock(side_effect=claim_after_two_locks)
        sleeps: list[float] = []
        service = ApplyPaymentReceiptService(
            get_receipt=self.service.get_receipt,
            claim_receipt=claim,
            create_payment=self.service.create_payment,
            fulfill_purchase=self.fulfill,
            mark_applied=self.service.mark_applied,
            now=lambda: self.now,
            sleep=sleeps.append,
            lock_retry_delay=lambda attempt: attempt / 10,
            ensure_transaction_boundary=self.service.ensure_transaction_boundary,
        )

        result = service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.assertFalse(result.is_replay)
        self.assertEqual(claim.call_count, 3)
        self.assertEqual(sleeps, [0.1, 0.2])

    def test_exhausted_sqlite_lock_becomes_domain_error(self) -> None:
        claim = Mock(side_effect=OperationalError("database is locked"))
        service = ApplyPaymentReceiptService(
            get_receipt=self.service.get_receipt,
            claim_receipt=claim,
            create_payment=self.service.create_payment,
            fulfill_purchase=self.fulfill,
            mark_applied=self.service.mark_applied,
            now=lambda: self.now,
            sleep=lambda _: None,
            lock_retry_delay=lambda _: 0,
            ensure_transaction_boundary=self.service.ensure_transaction_boundary,
        )

        with self.assertRaises(PaymentReceiptDatabaseBusy):
            service(receipt_id=self.receipt.pk, lease_id=self.lease_id)

        self.assertEqual(claim.call_count, 3)
        self.assertFalse(Payment.objects.exists())

    def test_non_lock_operational_error_is_not_hidden(self) -> None:
        claim = Mock(side_effect=OperationalError("disk I/O error"))
        sleeps: list[float] = []
        service = ApplyPaymentReceiptService(
            get_receipt=self.service.get_receipt,
            claim_receipt=claim,
            create_payment=self.service.create_payment,
            fulfill_purchase=self.fulfill,
            mark_applied=self.service.mark_applied,
            now=lambda: self.now,
            sleep=sleeps.append,
            lock_retry_delay=lambda _: 0,
            ensure_transaction_boundary=self.service.ensure_transaction_boundary,
        )

        with self.assertRaisesRegex(OperationalError, "disk I/O error"):
            service(receipt_id=self.receipt.pk, lease_id=self.lease_id)
        self.assertEqual(claim.call_count, 1)
        self.assertEqual(sleeps, [])

    def test_recognizes_canonical_sqlite_lock_and_busy_message_variants(self) -> None:
        variants = (
            "database is locked",
            "DATABASE   TABLE IS LOCKED: payments_paymentreceipt",
            "database schema is locked: main",
            "database is busy",
            "SQLITE_BUSY",
            "SQLITE_BUSY: database is locked",
            "SQLITE_LOCKED_SHAREDCACHE",
        )

        for message in variants:
            with self.subTest(message=message):
                self.assertTrue(_is_sqlite_lock_contention(OperationalError(message)))

    def test_prefers_structured_sqlite_busy_and_locked_codes(self) -> None:
        variants = (
            (sqlite3.SQLITE_BUSY, "SQLITE_BUSY"),
            (sqlite3.SQLITE_LOCKED, "SQLITE_LOCKED"),
            (sqlite3.SQLITE_BUSY | (1 << 8), "SQLITE_BUSY_RECOVERY"),
            (sqlite3.SQLITE_LOCKED | (1 << 8), "SQLITE_LOCKED_SHAREDCACHE"),
        )

        for errorcode, errorname in variants:
            with self.subTest(errorcode=errorcode, errorname=errorname):
                cause = sqlite3.OperationalError("opaque")
                cause.sqlite_errorcode = errorcode
                cause.sqlite_errorname = errorname
                wrapped = OperationalError("not a canonical lock message")
                wrapped.__cause__ = cause
                self.assertTrue(_is_sqlite_lock_contention(wrapped))

    def test_rejects_unrelated_or_lock_like_operational_errors(self) -> None:
        variants = (
            "disk I/O error",
            "database is malformed",
            "user account is locked",
            "database lock timeout from another backend",
            "busy processing application request",
            "SQLITE_CONSTRAINT",
        )

        for message in variants:
            with self.subTest(message=message):
                self.assertFalse(_is_sqlite_lock_contention(OperationalError(message)))

    def test_structured_non_contention_code_overrides_lock_like_message(self) -> None:
        cause = sqlite3.OperationalError("database is locked")
        cause.sqlite_errorcode = sqlite3.SQLITE_CONSTRAINT
        cause.sqlite_errorname = "SQLITE_CONSTRAINT"
        wrapped = OperationalError("database is locked")
        wrapped.__cause__ = cause

        self.assertFalse(_is_sqlite_lock_contention(wrapped))


class PaymentImportGraphTest(TestCase):
    def test_payments_package_does_not_import_vpn(self) -> None:
        payments_root = Path(__file__).resolve().parents[1]
        violations: list[str] = []
        for path in payments_root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(name == "apps.vpn" or name.startswith("apps.vpn.") for name in names):
                    violations.append(str(path.relative_to(payments_root)))
        self.assertEqual(violations, [])

    def test_apply_service_does_not_use_select_for_update(self) -> None:
        service_path = Path(__file__).resolve().parents[1] / "services" / "apply_payment_receipt.py"
        self.assertNotIn("select_for_update", service_path.read_text())
