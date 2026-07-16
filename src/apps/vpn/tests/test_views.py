from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.enums import (
    PaymentIntentStatusEnum,
    PaymentProviderEnum,
    PaymentReceiptStatusEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    PaymentIdentityConflict,
    PaymentIntentExpired,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
    VPNProductNotConfigured,
)
from apps.payments.tests.factories import (
    PaymentFactory,
    PaymentIntentFactory,
    PaymentReceiptFactory,
    ProductFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vpn.enums import VPNAccessState, VPNNodeHealthState
from apps.vpn.exceptions import (
    VPNAccessExpired,
    VPNAccessNotFound,
    VPNCapacityUnavailable,
    VPNReissueInProgress,
    VPNSalesDisabled,
)
from apps.vpn.tests.factories import VPNAccessFactory, VPNNodeFactory


@override_settings(
    VPN_SALES_ENABLED=True,
    VPN_AGENT_CONTRACT_VERSION="v1",
    VPN_PAYMENT_INTENT_TTL_SECONDS=900,
    VPN_SUBSCRIPTION_BASE_URL="https://vpn.example.com/api/v1/vpn/subscriptions",
)
class VPNBotAPIViewTest(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.client = APIClient()
        self.auth = {"HTTP_BOT_AUTH_TOKEN": settings.BOT_AUTH_TOKEN}
        self.user = SystemUserFactory(username="123")
        self.product = ProductFactory(
            code=ProductCodeEnum.VLESS_30D,
            title="VLESS VPN — 30 дней",
            description="Персональная VPN-подписка на 30 дней",
            currency="RUB",
            price=Decimal("199.00"),
            stars_price=150,
            provider_data='{"receipt": {"items": []}}',
            send_email_to_provider=True,
            need_email=True,
        )

    def _post(self, name: str, data: dict[str, object]):
        return self.client.post(reverse(name), data=data, format="json", **self.auth)

    def _ready_node(self) -> None:
        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            is_access_available=True,
            agent_contract_version="v1",
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )

    def assert_error(
        self,
        response,
        *,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(
            response.json(),
            {"code": code, "message": message, "detail": {}},
        )

    def test_all_bot_endpoints_require_bot_auth_token(self) -> None:
        requests = (
            ("vpn-payment-intent", {"username": "123", "currency": "RUB"}),
            (
                "vpn-pre-checkout",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "currency": "RUB",
                    "amount": 19_900,
                },
            ),
            (
                "vpn-payment",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "provider": "yukassa",
                    "charge_id": "charge-1",
                    "currency": "RUB",
                    "amount": 19_900,
                },
            ),
            ("vpn-status", {"username": "123"}),
            ("vpn-reissue", {"username": "123"}),
        )

        for name, data in requests:
            with self.subTest(name=name):
                response = self.client.post(reverse(name), data=data, format="json")
                self.assert_error(
                    response,
                    status_code=403,
                    code="forbidden",
                    message="Доступ запрещён",
                )

                response = self.client.post(
                    reverse(name),
                    data=data,
                    format="json",
                    HTTP_BOT_AUTH_TOKEN="wrong-secret-token",
                )
                self.assert_error(
                    response,
                    status_code=403,
                    code="forbidden",
                    message="Доступ запрещён",
                )

    def test_parser_and_internal_failures_use_safe_unified_errors(self) -> None:
        path = reverse("vpn-payment")
        unsafe_values = (
            b'{"invoice_payload": "raw-secret"',
            b'"scalar-secret"',
            b"\xff\xfe-secret",
        )

        for raw_body in unsafe_values:
            with (
                self.subTest(raw_body=raw_body),
                self.assertLogs("config.middlewares", level="INFO") as captured,
            ):
                response = self.client.generic(
                    "POST",
                    path,
                    data=raw_body,
                    content_type="application/json",
                    HTTP_BOT_AUTH_TOKEN=settings.BOT_AUTH_TOKEN,
                )
            self.assert_error(
                response,
                status_code=400,
                code="bad_payment_data",
                message="Некорректные данные платежа",
            )
            logs = "\n".join(captured.output)
            self.assertNotIn("raw-secret", logs)
            self.assertNotIn("scalar-secret", logs)
            self.assertNotIn("wrong-secret-token", logs)

        service = Mock(side_effect=RuntimeError("internal-provider-secret"))
        with patch(
            "apps.vpn.api.v1.views.bot.get_accept_vpn_payment_receipt_service",
            return_value=service,
        ):
            response = self._post(
                "vpn-payment",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "provider": "yukassa",
                    "charge_id": "charge-1",
                    "currency": "RUB",
                    "amount": 19_900,
                },
            )
        self.assert_error(
            response,
            status_code=500,
            code="internal_error",
            message="Временная внутренняя ошибка",
        )
        self.assertNotIn("internal-provider-secret", response.content.decode())

        response = self.client.get(reverse("vpn-status"), **self.auth)
        self.assert_error(
            response,
            status_code=405,
            code="method_not_allowed",
            message="Метод не поддерживается",
        )

    def test_every_request_rejects_unknown_fields_without_logging_values(self) -> None:
        secret = "unknown-nested-provider-secret"
        requests = (
            ("vpn-payment-intent", {"username": "123", "currency": "RUB"}),
            (
                "vpn-pre-checkout",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "currency": "RUB",
                    "amount": 19_900,
                },
            ),
            (
                "vpn-payment",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "provider": "yukassa",
                    "charge_id": "charge-1",
                    "currency": "RUB",
                    "amount": 19_900,
                },
            ),
            ("vpn-status", {"username": "123"}),
            ("vpn-reissue", {"username": "123"}),
        )

        for name, data in requests:
            with (
                self.subTest(name=name),
                self.assertLogs("config.middlewares", level="INFO") as captured,
            ):
                response = self._post(
                    name,
                    {
                        **data,
                        "provider_payload": {"unknown": secret},
                    },
                )
            self.assertEqual(
                response.status_code,
                400,
                msg=f"{name}: {response.content!r}",
            )
            self.assert_error(
                response,
                status_code=400,
                code="bad_payment_data",
                message="Некорректные данные платежа",
            )
            self.assertNotIn(secret, "\n".join(captured.output))

    def test_rub_payment_intent_returns_exact_telegram_invoice_fields(self) -> None:
        self._ready_node()

        response = self._post(
            "vpn-payment-intent", {"username": "123", "currency": "RUB"}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "title",
                "description",
                "invoice_payload",
                "currency",
                "provider",
                "provider_data",
                "send_email_to_provider",
                "need_email",
                "price",
                "expires_at",
            },
        )
        self.assertEqual(body["title"], self.product.title)
        self.assertEqual(body["description"], self.product.description)
        self.assertRegex(body["invoice_payload"], r"^[0-9a-f]{64}$")
        self.assertEqual(body["currency"], "RUB")
        self.assertEqual(body["provider"], "yukassa")
        self.assertEqual(body["provider_data"], {"receipt": {"items": []}})
        self.assertTrue(body["send_email_to_provider"])
        self.assertTrue(body["need_email"])
        self.assertEqual(body["price"], 19_900)
        self.assertNotIn("intent_id", body)

    def test_stars_payment_intent_returns_exact_telegram_invoice_fields(self) -> None:
        self._ready_node()

        response = self._post(
            "vpn-payment-intent", {"username": "123", "currency": "XTR"}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "title",
                "description",
                "invoice_payload",
                "currency",
                "provider",
                "stars_price",
                "expires_at",
            },
        )
        self.assertEqual(body["currency"], "XTR")
        self.assertEqual(body["provider"], "stars")
        self.assertEqual(body["stars_price"], 150)
        self.assertNotIn("provider_data", body)
        self.assertNotIn("intent_id", body)

    def test_invalid_request_is_safe_400_without_echoing_input(self) -> None:
        leaked = "provider-secret-payload"

        with self.assertLogs("config.middlewares", level="INFO") as captured:
            response = self._post(
                "vpn-payment",
                {
                    "username": "123",
                    "invoice_payload": leaked,
                    "provider": "invalid-provider",
                    "charge_id": "",
                    "currency": "USD",
                    "amount": 0,
                },
            )

        self.assert_error(
            response,
            status_code=400,
            code="bad_payment_data",
            message="Некорректные данные платежа",
        )
        self.assertNotIn(leaked, response.content.decode())
        rendered_logs = "\n".join(captured.output)
        self.assertNotIn(leaked, rendered_logs)
        self.assertNotIn(settings.BOT_AUTH_TOKEN, rendered_logs)

    def test_domain_errors_have_exact_safe_status_and_body(self) -> None:
        cases = (
            (
                "vpn-payment-intent",
                "get_create_vpn_payment_intent_service",
                VPNProductNotConfigured("123"),
                404,
                "vpn_product_not_configured",
                "VPN-продукт временно недоступен",
            ),
            (
                "vpn-payment-intent",
                "get_create_vpn_payment_intent_service",
                VPNSalesDisabled("123"),
                409,
                "vpn_sales_disabled",
                "Продажи VPN временно приостановлены",
            ),
            (
                "vpn-payment-intent",
                "get_create_vpn_payment_intent_service",
                VPNCapacityUnavailable("123"),
                503,
                "vpn_capacity_unavailable",
                "Сейчас нет доступных VPN-серверов",
            ),
            (
                "vpn-pre-checkout",
                "get_approve_vpn_payment_intent_service",
                PaymentIntentNotFound("123"),
                404,
                "payment_intent_not_found",
                "Намерение платежа не найдено",
            ),
            (
                "vpn-pre-checkout",
                "get_approve_vpn_payment_intent_service",
                PaymentIntentMismatch("123"),
                409,
                "payment_intent_mismatch",
                "Данные платежа не совпадают с выставленным счётом",
            ),
            (
                "vpn-pre-checkout",
                "get_approve_vpn_payment_intent_service",
                PaymentIntentExpired("123"),
                409,
                "payment_intent_expired",
                "Срок действия счёта истёк",
            ),
            (
                "vpn-payment",
                "get_accept_vpn_payment_receipt_service",
                BadPaymentData("123"),
                400,
                "bad_payment_data",
                "Некорректные данные платежа",
            ),
            (
                "vpn-payment",
                "get_accept_vpn_payment_receipt_service",
                PaymentIdentityConflict("123"),
                409,
                "payment_identity_conflict",
                "Идентификатор платежа уже связан с другими данными",
            ),
            (
                "vpn-reissue",
                "get_reissue_vpn_access_by_username_service",
                VPNAccessNotFound("123"),
                404,
                "vpn_access_not_found",
                "VPN-доступ не найден",
            ),
            (
                "vpn-reissue",
                "get_reissue_vpn_access_by_username_service",
                VPNAccessExpired("123"),
                409,
                "vpn_access_expired",
                "Срок VPN-доступа истёк",
            ),
            (
                "vpn-reissue",
                "get_reissue_vpn_access_by_username_service",
                VPNReissueInProgress("123"),
                409,
                "vpn_reissue_in_progress",
                "Перевыпуск VPN-доступа уже выполняется",
            ),
        )
        payloads = {
            "vpn-payment-intent": {"username": "123", "currency": "RUB"},
            "vpn-pre-checkout": {
                "username": "123",
                "invoice_payload": "a" * 64,
                "currency": "RUB",
                "amount": 19_900,
            },
            "vpn-payment": {
                "username": "123",
                "invoice_payload": "a" * 64,
                "provider": "yukassa",
                "charge_id": "charge-1",
                "currency": "RUB",
                "amount": 19_900,
            },
            "vpn-reissue": {"username": "123"},
        }

        for name, factory, error, status_code, code, message in cases:
            with (
                self.subTest(code=code),
                patch(f"apps.vpn.api.v1.views.bot.{factory}") as service_factory,
            ):
                service_factory.return_value.side_effect = error
                response = self._post(name, payloads[name])
                self.assert_error(
                    response,
                    status_code=status_code,
                    code=code,
                    message=message,
                )
                self.assertNotIn("123", response.content.decode())

    def test_pre_checkout_success_returns_only_approved_status(self) -> None:
        service = Mock(return_value=Mock(status="precheckout_approved"))
        with patch(
            "apps.vpn.api.v1.views.bot.get_approve_vpn_payment_intent_service",
            return_value=service,
        ):
            response = self._post(
                "vpn-pre-checkout",
                {
                    "username": "123",
                    "invoice_payload": "a" * 64,
                    "currency": "RUB",
                    "amount": 19_900,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "APPROVED"})

    @override_settings(VPN_SALES_ENABLED=False)
    def test_successful_payment_bypasses_current_flag_and_node_availability(
        self,
    ) -> None:
        intent = PaymentIntentFactory(
            user=self.user,
            product=self.product,
            status=PaymentIntentStatusEnum.APPROVED,
            currency="RUB",
            amount=19_900,
            provider=PaymentProviderEnum.YUKASSA,
            expires_at=timezone.now() - timedelta(days=1),
        )

        with patch("apps.vpn.factories.bot_api._schedule_receipt"):
            response = self._post(
                "vpn-payment",
                {
                    "username": "123",
                    "invoice_payload": intent.invoice_payload,
                    "provider": "yukassa",
                    "charge_id": "charge-rub",
                    "currency": "RUB",
                    "amount": 19_900,
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "ACCEPTED"})
        receipt = intent.receipt
        self.assertEqual(receipt.status, PaymentReceiptStatusEnum.RECEIVED)

    def test_applied_payment_replay_returns_200_without_internal_ids(self) -> None:
        intent = PaymentIntentFactory(
            user=self.user,
            product=self.product,
            status=PaymentIntentStatusEnum.PAID,
            currency="XTR",
            amount=150,
            provider=PaymentProviderEnum.STARS,
        )
        payment = PaymentFactory(
            user=self.user,
            product=self.product,
            provider=PaymentProviderEnum.STARS,
            charge_id="charge-stars",
        )
        PaymentReceiptFactory(
            intent=intent,
            user=self.user,
            product=self.product,
            provider=PaymentProviderEnum.STARS,
            charge_id="charge-stars",
            currency="XTR",
            amount=150,
            status=PaymentReceiptStatusEnum.APPLIED,
            payment=payment,
        )

        response = self._post(
            "vpn-payment",
            {
                "username": "123",
                "invoice_payload": intent.invoice_payload,
                "provider": "stars",
                "charge_id": "charge-stars",
                "currency": "XTR",
                "amount": 150,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "APPLIED"})

    def test_status_has_exact_states_and_url_only_for_ready(self) -> None:
        response = self._post("vpn-status", {"username": "missing"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "NOT_PURCHASED"})

        access = VPNAccessFactory(user=self.user, state=VPNAccessState.PREPARING)
        response = self._post("vpn-status", {"username": "123"})
        self.assertEqual(response.json()["status"], "PREPARING")
        self.assertNotIn("subscription_url", response.json())

        credential = uuid.uuid4()
        access.state = VPNAccessState.READY
        access.published_uuid = credential
        access.desired_uuid = credential
        access.published_revision = access.desired_revision
        access.save()
        response = self._post("vpn-status", {"username": "123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "READY")
        self.assertEqual(
            response.json()["subscription_url"],
            f"https://vpn.example.com/api/v1/vpn/subscriptions/{access.subscription_token}/",
        )
        self.assertIn("expired_at", response.json())

        access.state = VPNAccessState.EXPIRED
        access.expired_at = timezone.now() - timedelta(seconds=1)
        access.save()
        response = self._post("vpn-status", {"username": "123"})
        self.assertEqual(response.json()["status"], "EXPIRED")
        self.assertNotIn("subscription_url", response.json())

        access.state = VPNAccessState.DISABLED_REFUND
        access.disabled_at = timezone.now()
        access.disabled_by = self.user
        access.disabled_reason = "refund"
        access.save()
        response = self._post("vpn-status", {"username": "123"})
        self.assertEqual(response.json()["status"], "DISABLED")
        self.assertNotIn("subscription_url", response.json())

    def test_inactive_access_is_absent_for_status_and_reissue(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            user=self.user,
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
            is_active=False,
        )

        response = self._post("vpn-status", {"username": "123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "NOT_PURCHASED"})
        self.assertNotIn(access.subscription_token, response.content.decode())

        response = self._post("vpn-reissue", {"username": "123"})
        self.assert_error(
            response,
            status_code=404,
            code="vpn_access_not_found",
            message="VPN-доступ не найден",
        )

    def test_reissue_returns_preparing_and_preserves_subscription_url(self) -> None:
        credential = uuid.uuid4()
        access = VPNAccessFactory(
            user=self.user,
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
        )
        original_token = access.subscription_token

        with patch("apps.vpn.services.reissue._schedule_reconcile"):
            response = self._post("vpn-reissue", {"username": "123"})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "PREPARING"})
        access.refresh_from_db()
        self.assertEqual(access.state, VPNAccessState.PREPARING)
        self.assertEqual(access.subscription_token, original_token)
        self.assertNotEqual(access.desired_uuid, credential)
