from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.conf import settings
from django.db import OperationalError
from django.test import TestCase, override_settings

from apps.payments.clients import CryptoPayClient
from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    CryptoInvoiceUnavailable,
    CryptoPayClientError,
    ProductNotFound,
)
from apps.payments.models import CryptoPaymentIntent, Product
from apps.payments.services.create_crypto_invoice import (
    CreateOrReuseCryptoInvoiceService,
)
from apps.payments.services.dtos import (
    CreateCryptoInvoiceIn,
    CreateCryptoInvoiceOut,
    CryptoInvoiceDTO,
)
from apps.payments.tests.factories import (
    CryptoPaymentIntentFactory,
    ProductFactory,
    make_crypto_invoice,
)
from apps.users.tests.factories import SystemUserFactory


@override_settings(CRYPTOPAY_REQUEST_TIMEOUT=5.0)
class TestCreateOrReuseCryptoInvoiceService(TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        self.user = SystemUserFactory(username="1487189460")
        self.client = Mock(spec=CryptoPayClient)
        self.service = CreateOrReuseCryptoInvoiceService(
            crypto_pay_client=self.client,
            clock=lambda: self.now,
        )

    def _request(self, kind: str = PaymentKindEnum.SUBSCRIPTION) -> CreateCryptoInvoiceIn:
        return CreateCryptoInvoiceIn(username=self.user.username, purchase_kind=kind)

    def _valid_invoice(self, *, amount: Decimal, payload: str) -> CryptoInvoiceDTO:
        return make_crypto_invoice(
            status="active",
            paid_asset=None,
            paid_at=None,
            amount=amount,
            payload=payload,
            created_at=self.now,
            expiration_date=self.now + timedelta(seconds=1800),
        )

    def _create_valid_invoice(
        self, *, amount: Decimal, payload: str, description: str
    ) -> CryptoInvoiceDTO:
        return self._valid_invoice(amount=amount, payload=payload)

    def test_maps_kind_and_converts_kopecks_exactly(self) -> None:
        cases = (
            (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
            (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D, "14900", "149.00"),
            (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D, "9900", "99.00"),
        )
        for kind, product_code, kopecks, rubles in cases:
            with self.subTest(kind=kind):
                Product.objects.all().delete()
                CryptoPaymentIntent.objects.all().delete()
                self.client.reset_mock()
                self.client.create_invoice.side_effect = self._create_valid_invoice
                ProductFactory(code=product_code, price=Decimal(kopecks), currency="RUB")
                result = self.service(request=self._request(kind))
                self.assertEqual(result.rub_amount, Decimal(rubles))
                call = self.client.create_invoice.call_args.kwargs
                self.assertEqual(call["amount"], Decimal(rubles))
                self.assertNotIn(self.user.username, call["payload"])
                self.assertEqual(
                    call["payload"], str(CryptoPaymentIntent.objects.get().public_id)
                )

    def test_active_invoice_is_reused_without_provider_call(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.user,
            purchase_kind=PaymentKindEnum.SUBSCRIPTION,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=self.now + timedelta(minutes=5),
            provider_invoice_url="https://t.me/CryptoBot?start=reuse",
            rub_amount=Decimal("99.00"),
        )
        result = self.service(request=self._request())
        self.assertEqual(
            result,
            CreateCryptoInvoiceOut(
                invoice_url=intent.provider_invoice_url,
                rub_amount=intent.rub_amount,
                expires_at=intent.provider_expires_at,
                reused=True,
            ),
        )
        self.client.create_invoice.assert_not_called()

    def test_expired_invoice_becomes_local_expired_and_uses_new_price_snapshot(self) -> None:
        expired = CryptoPaymentIntentFactory(
            initiator=self.user,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_expires_at=self.now,
            provider_invoice_url="https://t.me/CryptoBot?start=expired",
            rub_amount=Decimal("99.00"),
        )
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("14900"))
        self.client.create_invoice.side_effect = self._create_valid_invoice
        result = self.service(request=self._request())
        expired.refresh_from_db()
        self.assertEqual(expired.status, CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED)
        self.assertEqual(result.rub_amount, Decimal("149.00"))
        self.assertFalse(result.reused)
        self.assertEqual(CryptoPaymentIntent.objects.count(), 2)

    def test_rejects_unknown_user_or_purchase_kind_before_reservation(self) -> None:
        cases = (
            CreateCryptoInvoiceIn(username="missing", purchase_kind="subscription"),
            self._request("arbitrary_product"),
        )
        for request in cases:
            with self.subTest(request=request):
                with self.assertRaises(BadPaymentData) as raised:
                    self.service(request=request)
                self.assertEqual(raised.exception.context["reason_code"], "invalid_purchase")
        self.assertFalse(CryptoPaymentIntent.objects.exists())
        self.client.create_invoice.assert_not_called()

    def test_missing_or_inactive_product_is_rejected_without_reservation(self) -> None:
        for inactive in (False, True):
            with self.subTest(inactive=inactive):
                Product.objects.all().delete()
                if inactive:
                    ProductFactory(code=ProductCodeEnum.MTPROTO_30D, is_active=False)
                with self.assertRaises(ProductNotFound):
                    self.service(request=self._request())
                self.assertFalse(CryptoPaymentIntent.objects.exists())
                self.client.create_invoice.assert_not_called()

    def test_invalid_currency_or_price_is_rejected_without_reservation(self) -> None:
        cases = (
            ("USD", Decimal("9900"), "invalid_currency"),
            ("RUB", Decimal("0"), "invalid_price"),
            ("RUB", Decimal("-1"), "invalid_price"),
            ("RUB", Decimal("9900.50"), "invalid_price"),
        )
        for currency, price, reason_code in cases:
            with self.subTest(currency=currency, price=price):
                Product.objects.all().delete()
                ProductFactory(
                    code=ProductCodeEnum.MTPROTO_30D,
                    currency=currency,
                    price=price,
                )
                with self.assertRaises(BadPaymentData) as raised:
                    self.service(request=self._request())
                self.assertEqual(raised.exception.context["reason_code"], reason_code)
                self.assertFalse(CryptoPaymentIntent.objects.exists())
                self.client.create_invoice.assert_not_called()

    def test_provider_failure_marks_creating_intent_failed_and_allows_retry(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_invoice.side_effect = CryptoPayClientError("cryptopay_timeout")
        with self.assertRaises(CryptoInvoiceUnavailable) as raised:
            self.service(request=self._request())
        intent = CryptoPaymentIntent.objects.get()
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.CREATE_FAILED)
        self.assertEqual(intent.last_error_code, "cryptopay_timeout")
        self.assertEqual(raised.exception.context["reason_code"], "cryptopay_timeout")
        self.client.create_invoice.side_effect = self._create_valid_invoice
        self.assertFalse(self.service(request=self._request()).reused)

    @patch("apps.payments.services.create_crypto_invoice.sleep")
    def test_activation_lock_exhaustion_fails_intent_without_repeating_provider(
        self, sleep: Mock
    ) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_invoice.side_effect = self._create_valid_invoice
        locked = OperationalError("database table is locked")
        with patch(
            "apps.payments.services.create_crypto_invoice.activate_crypto_intent_from_provider",
            side_effect=locked,
        ) as activate, self.assertRaises(CryptoInvoiceUnavailable) as raised:
            self.service(request=self._request())
        intent = CryptoPaymentIntent.objects.get()
        self.assertEqual(activate.call_count, 5)
        self.assertEqual(self.client.create_invoice.call_count, 1)
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.CREATE_FAILED)
        self.assertEqual(intent.last_error_code, "database_locked")
        self.assertEqual(raised.exception.context["reason_code"], "database_locked")
        self.assertIs(raised.exception.__cause__, locked)
        self.assertEqual(sleep.call_count, 4)

    @patch("apps.payments.services.create_crypto_invoice.sleep")
    def test_provider_failure_transition_lock_exhaustion_returns_safe_domain_error(
        self, sleep: Mock
    ) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_invoice.side_effect = CryptoPayClientError("cryptopay_timeout")
        locked = OperationalError("database table is locked")
        with patch(
            "apps.payments.services.create_crypto_invoice.fail_crypto_intent_creation",
            side_effect=locked,
        ) as fail, self.assertRaises(CryptoInvoiceUnavailable) as raised:
            self.service(request=self._request())
        self.assertEqual(fail.call_count, 5)
        self.assertEqual(self.client.create_invoice.call_count, 1)
        self.assertEqual(raised.exception.context["reason_code"], "database_locked")
        self.assertIs(raised.exception.__cause__, locked)
        self.assertEqual(sleep.call_count, 4)

    def test_stale_creating_lease_at_exact_timeout_boundary_becomes_retryable(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        stale = CryptoPaymentIntentFactory(initiator=self.user)
        exact_boundary = self.now - timedelta(seconds=2 * settings.CRYPTOPAY_REQUEST_TIMEOUT)
        CryptoPaymentIntent.objects.filter(pk=stale.pk).update(created_at=exact_boundary)
        self.client.create_invoice.side_effect = self._create_valid_invoice
        result = self.service(request=self._request())
        stale.refresh_from_db()
        self.assertEqual(stale.status, CryptoPaymentIntentStatusEnum.CREATE_FAILED)
        self.assertEqual(stale.last_error_code, "creating_stale")
        self.assertFalse(result.reused)
        active = CryptoPaymentIntent.objects.filter(status=CryptoPaymentIntentStatusEnum.ACTIVE)
        self.assertEqual(active.count(), 1)

    def test_validated_create_response_activates_with_matching_positive_invoice_id(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))
        self.client.create_invoice.side_effect = self._create_valid_invoice
        result = self.service(request=self._request())
        intent = CryptoPaymentIntent.objects.get()
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.ACTIVE)
        self.assertEqual(intent.provider_invoice_id, 731)
        self.assertEqual(intent.provider_invoice_url, "https://t.me/CryptoBot?start=test")
        self.assertEqual(intent.provider_created_at, self.now)
        self.assertEqual(intent.provider_expires_at, self.now + timedelta(seconds=1800))
        self.assertEqual(
            result,
            CreateCryptoInvoiceOut(
                invoice_url=intent.provider_invoice_url,
                rub_amount=Decimal("99.00"),
                expires_at=intent.provider_expires_at,
                reused=False,
            ),
        )

    def test_create_response_mismatch_fails_creating_intent_without_returning_url(self) -> None:
        naive = datetime(2026, 8, 2, 12, 0)
        cases = (
            ("create_invoice_id_invalid", {"invoice_id": 0}),
            ("create_invoice_id_invalid", {"invoice_id": "731"}),
            ("create_status_invalid", {"status": "paid"}),
            ("create_payload_mismatch", {"payload": "wrong-public-id"}),
            ("create_currency_type_mismatch", {"currency_type": "crypto"}),
            ("create_fiat_mismatch", {"fiat": "USD"}),
            ("create_amount_mismatch", {"amount": Decimal("99.01")}),
            ("create_assets_mismatch", {"accepted_assets": frozenset({"USDT"})}),
            ("create_already_paid", {"paid_asset": "USDT"}),
            ("create_already_paid", {"paid_at": self.now}),
            ("create_url_invalid", {"bot_invoice_url": "http://t.me/CryptoBot?start=test"}),
            ("create_timestamp_invalid", {"created_at": naive}),
            ("create_timestamp_invalid", {"expiration_date": naive}),
            ("create_expiration_invalid", {"expiration_date": self.now}),
            (
                "create_expiration_invalid",
                {"expiration_date": self.now + timedelta(seconds=1799)},
            ),
        )
        for reason_code, changes in cases:
            with self.subTest(reason_code=reason_code, changes=changes):
                Product.objects.all().delete()
                CryptoPaymentIntent.objects.all().delete()
                ProductFactory(code=ProductCodeEnum.MTPROTO_30D, price=Decimal("9900"))

                def mismatch(
                    *, amount: Decimal, payload: str, description: str
                ) -> CryptoInvoiceDTO:
                    return replace(
                        self._valid_invoice(amount=amount, payload=payload), **changes
                    )

                self.client.create_invoice.side_effect = mismatch
                with self.assertRaises(CryptoInvoiceUnavailable) as raised:
                    self.service(request=self._request())
                intent = CryptoPaymentIntent.objects.get()
                self.assertEqual(raised.exception.context["reason_code"], reason_code)
                self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.CREATE_FAILED)
                self.assertEqual(intent.last_error_code, reason_code)
                self.assertIsNone(intent.provider_invoice_id)
                self.assertEqual(intent.provider_invoice_url, "")
                active = CryptoPaymentIntent.objects.filter(status=CryptoPaymentIntentStatusEnum.ACTIVE)
                self.assertFalse(active.exists())
