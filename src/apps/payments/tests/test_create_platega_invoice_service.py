from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.db import OperationalError, connection
from django.test import TestCase, override_settings

from apps.payments.clients import PlategaClient
from apps.payments.enums import PaymentKindEnum, PlategaPaymentIntentStatusEnum, ProductCodeEnum
from apps.payments.exceptions import (
    BadPaymentData,
    PlategaClientError,
    PlategaInvoiceCreationInProgress,
    PlategaInvoiceUnavailable,
)
from apps.payments.models import PlategaPaymentIntent, Product
from apps.payments.services.create_platega_invoice import CreateOrReusePlategaInvoiceService
from apps.payments.services.dtos import (
    CreatePlategaInvoiceIn,
    CreatePlategaInvoiceOut,
    PlategaTransactionDTO,
)
from apps.payments.tests.factories import PlategaPaymentIntentFactory, ProductFactory
from apps.users.tests.factories import SystemUserFactory


@override_settings(PLATEGA_REQUEST_TIMEOUT=5.0)
class TestCreateOrReusePlategaInvoiceService(TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.user = SystemUserFactory(username="1487189460", telegram_username="saved_name")
        self.client = Mock(spec=PlategaClient)
        self.service = CreateOrReusePlategaInvoiceService(
            platega_client=self.client,
            clock=lambda: self.now,
        )

    def _request(self, kind: str = PaymentKindEnum.SUBSCRIPTION) -> CreatePlategaInvoiceIn:
        return CreatePlategaInvoiceIn(username=self.user.username, purchase_kind=kind)

    def _transaction(self, **changes: object) -> PlategaTransactionDTO:
        values: dict[str, object] = {
            "transaction_id": uuid4(),
            "status": "PENDING",
            "redirect_url": "https://pay.example/transaction",
            "expires_in": timedelta(minutes=15),
        }
        values.update(changes)
        return PlategaTransactionDTO(**values)

    def test_maps_each_kind_snapshots_kopecks_and_uses_stored_username(self) -> None:
        cases = (
            (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
            (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D, "14900", "149.00"),
            (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
        )
        for kind, product_code, kopecks, rubles in cases:
            with self.subTest(kind=kind):
                Product.objects.all().delete()
                PlategaPaymentIntent.objects.all().delete()
                ProductFactory(code=product_code, price=Decimal(kopecks))
                self.client.reset_mock()
                self.client.create_transaction.return_value = self._transaction()
                result = self.service(request=self._request(kind))
                self.assertEqual(result.rub_amount, Decimal(rubles))
                call = self.client.create_transaction.call_args.kwargs
                self.assertEqual(call["amount"], Decimal(rubles))
                self.assertEqual(call["telegram_id"], self.user.username)
                self.assertEqual(call["telegram_username"], "saved_name")
                self.assertEqual(call["return_url"], settings.BOT_LINK)
                self.assertEqual(
                    call["public_id"], PlategaPaymentIntent.objects.get().public_id
                )

    def test_falls_back_to_telegram_id_when_saved_username_is_empty(self) -> None:
        self.user.telegram_username = ""
        self.user.save(update_fields=["telegram_username"])
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_transaction.return_value = self._transaction()
        self.service(request=self._request())
        self.assertEqual(
            self.client.create_transaction.call_args.kwargs["telegram_username"],
            self.user.username,
        )

    def test_reuses_live_link_without_provider_call(self) -> None:
        intent = PlategaPaymentIntentFactory(
            initiator=self.user,
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=self.now + timedelta(minutes=1),
            provider_payment_url="https://pay.example/live",
            rub_amount=Decimal("99.00"),
        )
        self.assertEqual(
            self.service(request=self._request()),
            CreatePlategaInvoiceOut(
                payment_url=intent.provider_payment_url,
                rub_amount=intent.rub_amount,
                expires_at=intent.provider_expires_at,
                reused=True,
            ),
        )
        self.client.create_transaction.assert_not_called()

    def test_expired_canceled_and_failed_intents_allow_new_price_snapshot(self) -> None:
        cases = (
            (PlategaPaymentIntentStatusEnum.ACTIVE, self.now),
            (PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED, None),
            (PlategaPaymentIntentStatusEnum.CREATE_FAILED, None),
        )
        for old_status, old_expiry in cases:
            with self.subTest(old_status=old_status):
                PlategaPaymentIntent.objects.all().delete()
                Product.objects.all().delete()
                old = PlategaPaymentIntentFactory(
                    initiator=self.user,
                    status=old_status,
                    provider_expires_at=old_expiry,
                )
                ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("14900"))
                self.client.reset_mock()
                self.client.create_transaction.return_value = self._transaction()
                result = self.service(request=self._request())
                old.refresh_from_db()
                self.assertFalse(result.reused)
                self.assertEqual(result.rub_amount, Decimal("149.00"))
                if old_status == PlategaPaymentIntentStatusEnum.ACTIVE:
                    self.assertEqual(old.status, PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED)

    def test_rejects_invalid_product_currency_or_non_integral_kopecks(self) -> None:
        for currency, price, reason_code in (
            ("USD", Decimal("9900"), "invalid_currency"),
            ("RUB", Decimal("0"), "invalid_price"),
            ("RUB", Decimal("9900.50"), "invalid_price"),
        ):
            with self.subTest(currency=currency, price=price):
                Product.objects.all().delete()
                ProductFactory(code=ProductCodeEnum.MTPROTO_30D, currency=currency, price=price)
                with self.assertRaises(BadPaymentData) as raised:
                    self.service(request=self._request())
                self.assertEqual(raised.exception.context["reason_code"], reason_code)
                self.assertFalse(PlategaPaymentIntent.objects.exists())

    def test_current_creating_processing_or_retryable_is_a_safe_conflict(self) -> None:
        for status_value in (
            PlategaPaymentIntentStatusEnum.CREATING,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ):
            with self.subTest(status=status_value):
                PlategaPaymentIntent.objects.all().delete()
                PlategaPaymentIntentFactory(initiator=self.user, status=status_value)
                with self.assertRaises(PlategaInvoiceCreationInProgress) as raised:
                    self.service(request=self._request())
                self.assertEqual(raised.exception.context["reason_code"], status_value)
                self.client.create_transaction.assert_not_called()

    def test_provider_failure_marks_reservation_failed_and_returns_safe_503_error(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_transaction.side_effect = PlategaClientError("timeout")
        with self.assertRaises(PlategaInvoiceUnavailable) as raised:
            self.service(request=self._request())
        intent = PlategaPaymentIntent.objects.get()
        self.assertEqual(intent.status, PlategaPaymentIntentStatusEnum.CREATE_FAILED)
        self.assertEqual(intent.last_error_code, "timeout")
        self.assertEqual(raised.exception.context, {"reason_code": "timeout"})

    def test_provider_call_is_outside_database_transaction(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        outer_atomic_depth = len(connection.atomic_blocks)

        def create_transaction(**_: object) -> PlategaTransactionDTO:
            self.assertEqual(len(connection.atomic_blocks), outer_atomic_depth)
            return self._transaction()

        self.client.create_transaction.side_effect = create_transaction
        self.service(request=self._request())

    def test_storage_failure_returns_safe_unavailable_error(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_transaction.return_value = self._transaction()
        with patch(
            "apps.payments.services.create_platega_invoice.activate_platega_intent_from_provider",
            side_effect=OperationalError("database table is locked"),
        ), self.assertRaises(PlategaInvoiceUnavailable) as raised:
            self.service(request=self._request())
        self.assertEqual(raised.exception.context["reason_code"], "database_locked")

    def test_early_storage_failures_return_safe_unavailable_without_provider_call(self) -> None:
        cases = (
            "get_user_by_username",
            "get_reusable_platega_intent",
        )
        for selector_name in cases:
            with self.subTest(selector_name=selector_name), patch(
                f"apps.payments.services.create_platega_invoice.{selector_name}",
                side_effect=OperationalError("database is unavailable"),
            ), self.assertRaises(PlategaInvoiceUnavailable) as raised:
                self.service(request=self._request())
            self.assertEqual(raised.exception.context, {"reason_code": "database_error"})
            self.client.create_transaction.assert_not_called()

    def test_database_lock_without_confirmed_reservation_winner_returns_503(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        with patch(
            "apps.payments.services.create_platega_invoice.reserve_platega_intent_or_read_winner",
            side_effect=OperationalError("database table is locked"),
        ), self.assertRaises(PlategaInvoiceUnavailable) as raised:
            self.service(request=self._request())
        self.assertEqual(raised.exception.context, {"reason_code": "database_locked"})
        self.client.create_transaction.assert_not_called()
