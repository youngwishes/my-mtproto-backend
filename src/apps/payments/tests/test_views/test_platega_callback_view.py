from __future__ import annotations

import secrets
from dataclasses import asdict
from decimal import Decimal
from unittest import mock
from uuid import UUID, uuid4

from django.db import OperationalError
from django.test import override_settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APITestCase

from apps.payments.api.v1.serializers import PlategaCallbackSerializer
from apps.payments.enums import PlategaPaymentIntentStatusEnum
from apps.payments.exceptions import PlategaPaymentRetryable
from apps.payments.services.dtos import (
    ApplyPlategaPaymentOut,
    PlategaCallbackWarningDTO,
    ValidatePlategaCallbackOut,
)
from apps.payments.tests.factories import PlategaPaymentIntentFactory


_VIEW = "apps.payments.api.v1.views.platega_views"
_URL = "/api/v1/payments/platega/callback/"
_MERCHANT_ID = "test-merchant"
_SECRET = "test-secret"
_TRANSACTION_ID = UUID("6765c89d-4800-4e07-b45d-d886e696e87c")


@override_settings(
    PLATEGA_MERCHANT_ID=_MERCHANT_ID,
    PLATEGA_SECRET=_SECRET,
)
class TestPlategaCallbackDiagnostics(APITestCase):
    body = '{"amount":"99.0036"}'

    def post_callback(
        self,
        *,
        merchant_id: str = _MERCHANT_ID,
        secret: str = _SECRET,
    ):
        return self.client.generic(
            "POST",
            _URL,
            self.body.encode(),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer private-authorization",
            HTTP_COOKIE="sessionid=private-cookie",
            HTTP_USER_AGENT="Platega Payment",
            HTTP_X_MERCHANTID=merchant_id,
            HTTP_X_SECRET=secret,
        )

    @override_settings(PLATEGA_CALLBACK_DEBUG_LOGGING=True)
    def test_authenticated_callback_logs_raw_shape_without_header_values(
        self,
    ) -> None:
        with self.assertLogs(_VIEW, level="INFO") as captured:
            response = self.post_callback()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rendered = "\n".join(captured.output)
        for expected in (
            "platega_callback_request",
            "'method': 'POST'",
            f"'path': '{_URL}'",
            "'content_type': 'application/json'",
            "'user_agent': 'Platega Payment'",
            "'header_names'",
            "Authorization",
            "Cookie",
            "X-Merchantid",
            "X-Secret",
            f"'body': '{self.body}'",
        ):
            self.assertIn(expected, rendered)
        for forbidden in (
            _MERCHANT_ID,
            _SECRET,
            "private-authorization",
            "private-cookie",
        ):
            self.assertNotIn(forbidden, rendered)

    @override_settings(PLATEGA_CALLBACK_DEBUG_LOGGING=False)
    def test_diagnostic_flag_disabled_emits_no_callback_log(self) -> None:
        with self.assertNoLogs(_VIEW, level="INFO"):
            response = self.post_callback()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PLATEGA_CALLBACK_DEBUG_LOGGING=True)
    def test_invalid_credentials_emit_no_callback_log(self) -> None:
        with self.assertNoLogs(_VIEW, level="INFO"):
            response = self.post_callback(secret="wrong-secret")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    PLATEGA_MERCHANT_ID=_MERCHANT_ID,
    PLATEGA_SECRET=_SECRET,
)
class TestPlategaCallbackView(APITestCase):
    def setUp(self) -> None:
        self.intent = PlategaPaymentIntentFactory(
            status=PlategaPaymentIntentStatusEnum.ACTIVE,
            provider_transaction_id=_TRANSACTION_ID,
            rub_amount=Decimal("99.00"),
            currency="RUB",
            payment_method=2,
            provider_payment_url="https://pay.example/private-result",
        )
        self.apply = mock.Mock(
            return_value=ApplyPlategaPaymentOut(
                fulfilled=True,
                already_fulfilled=False,
            )
        )
        self.get_apply = mock.patch(
            f"{_VIEW}.get_apply_platega_payment_service",
            return_value=self.apply,
        ).start()
        self.logger = mock.patch(f"{_VIEW}.logger").start()
        self.addCleanup(mock.patch.stopall)

    @staticmethod
    def payload(**updates: object) -> dict[str, object]:
        data: dict[str, object] = {
            "id": str(_TRANSACTION_ID),
            "amount": 99,
            "currency": "RUB",
            "status": "CONFIRMED",
            "paymentMethod": 2,
        }
        data.update(updates)
        return data

    def post_payload(
        self,
        payload: object,
        *,
        merchant_id: str | None = _MERCHANT_ID,
        secret: str | None = _SECRET,
    ):
        headers: dict[str, str] = {}
        if merchant_id is not None:
            headers["HTTP_X_MERCHANTID"] = merchant_id
        if secret is not None:
            headers["HTTP_X_SECRET"] = secret
        return self.client.post(_URL, payload, format="json", **headers)

    def post_raw_json(
        self,
        body: str,
        *,
        merchant_id: str | None = _MERCHANT_ID,
        secret: str | None = _SECRET,
    ):
        headers: dict[str, str] = {}
        if merchant_id is not None:
            headers["HTTP_X_MERCHANTID"] = merchant_id
        if secret is not None:
            headers["HTTP_X_SECRET"] = secret
        return self.client.generic(
            "POST",
            _URL,
            body.encode(),
            content_type="application/json",
            **headers,
        )

    @staticmethod
    def raw_callback(amount: str) -> str:
        return (
            f'{{"id":"{_TRANSACTION_ID}","amount":{amount},'
            '"currency":"RUB","status":"CONFIRMED","paymentMethod":2}'
        )

    def assert_no_domain_processing(self) -> None:
        self.get_apply.assert_not_called()
        self.logger.warning.assert_not_called()

    def test_authentication_evaluates_both_headers_before_body_parsing(self) -> None:
        with mock.patch(
            f"{_VIEW}.secrets.compare_digest",
            side_effect=(False, True),
        ) as compare, mock.patch.object(
            Request,
            "_load_data_and_files",
        ) as parse:
            response = self.client.generic(
                "POST",
                _URL,
                b'{"private":"body"}',
                content_type="application/json",
                HTTP_X_MERCHANTID="wrong-merchant",
                HTTP_X_SECRET=_SECRET,
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            compare.call_args_list,
            [
                mock.call(b"wrong-merchant", _MERCHANT_ID.encode()),
                mock.call(_SECRET.encode(), _SECRET.encode()),
            ],
        )
        parse.assert_not_called()
        self.assert_no_domain_processing()

    def test_non_ascii_credentials_are_compared_as_bytes_before_body_parsing(
        self,
    ) -> None:
        with mock.patch(
            f"{_VIEW}.secrets.compare_digest",
            wraps=secrets.compare_digest,
        ) as compare, mock.patch.object(
            Request,
            "_load_data_and_files",
        ) as parse:
            response = self.client.generic(
                "POST",
                _URL,
                b'{"private":"body"}',
                content_type="application/json",
                HTTP_X_MERCHANTID="неверный-merchant",
                HTTP_X_SECRET="неверный-secret-💥",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            compare.call_args_list,
            [
                mock.call("неверный-merchant".encode(), _MERCHANT_ID.encode()),
                mock.call("неверный-secret-💥".encode(), _SECRET.encode()),
            ],
        )
        parse.assert_not_called()
        self.assert_no_domain_processing()

    def test_blank_configured_credentials_fail_closed_after_both_checks(self) -> None:
        cases = (("", _SECRET), (_MERCHANT_ID, ""), ("", ""))
        for configured_merchant, configured_secret in cases:
            with self.subTest(
                configured_merchant=configured_merchant,
                configured_secret=configured_secret,
            ), override_settings(
                PLATEGA_MERCHANT_ID=configured_merchant,
                PLATEGA_SECRET=configured_secret,
            ), mock.patch(
                f"{_VIEW}.secrets.compare_digest",
                return_value=True,
            ) as compare:
                response = self.post_payload(self.payload())

            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(compare.call_count, 2)
            self.assert_no_domain_processing()

    def test_missing_or_invalid_credentials_are_401(self) -> None:
        cases = (
            (None, _SECRET),
            (_MERCHANT_ID, None),
            (None, None),
            ("wrong-merchant", _SECRET),
            (_MERCHANT_ID, "wrong-secret"),
            ("wrong-merchant", "wrong-secret"),
        )
        for merchant_id, secret in cases:
            with self.subTest(merchant_id=merchant_id, secret=secret):
                response = self.post_payload(
                    self.payload(),
                    merchant_id=merchant_id,
                    secret=secret,
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                )
                self.assert_no_domain_processing()

    def test_authenticated_invalid_json_is_empty_safe_200(self) -> None:
        with mock.patch(
            f"{_VIEW}.get_validate_platega_callback_service"
        ) as get_validator:
            response = self.client.generic(
                "POST",
                _URL,
                b'{"id":',
                content_type="application/json",
                HTTP_X_MERCHANTID=_MERCHANT_ID,
                HTTP_X_SECRET=_SECRET,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")
        get_validator.assert_not_called()
        self.assert_no_domain_processing()

    def test_authenticated_extra_or_malformed_payload_is_empty_safe_200(self) -> None:
        cases = (
            self.payload(extra="not-accepted"),
            {key: value for key, value in self.payload().items() if key != "id"},
            self.payload(id="not-a-uuid"),
            self.payload(amount="not-decimal"),
            self.payload(paymentMethod="not-integer"),
            [self.payload()],
        )
        with mock.patch(f"{_VIEW}.get_validate_platega_callback_service") as factory:
            for payload in cases:
                with self.subTest(payload=payload):
                    response = self.post_payload(payload)
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.content, b"")
            factory.assert_not_called()

        self.assert_no_domain_processing()

    def test_raw_finite_json_numbers_reach_validator_as_exact_decimals(self) -> None:
        huge_integer = "1" * 5000
        cases = (
            ("99", Decimal("99")),
            ("99.0036", Decimal("99.0036")),
            (
                "99.0000000000000000000000000000000000000001",
                Decimal("99.0000000000000000000000000000000000000001"),
            ),
            ("9.90036e1", Decimal("99.0036")),
            (huge_integer, Decimal(huge_integer)),
        )
        validator = mock.Mock(
            return_value=ValidatePlategaCallbackOut(
                payment=None,
                reason_code="canceled",
                warning=None,
            )
        )
        with mock.patch(
            f"{_VIEW}.get_validate_platega_callback_service",
            return_value=validator,
        ):
            for amount_token, expected in cases:
                with self.subTest(amount_token=amount_token[:40]):
                    validator.reset_mock()
                    response = self.post_raw_json(
                        self.raw_callback(amount_token),
                    )

                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.content, b"")
                    validator.assert_called_once()
                    self.assertEqual(
                        validator.call_args.kwargs["callback"].amount,
                        expected,
                    )

        self.assert_no_domain_processing()

    def test_raw_precise_overpayment_is_fulfilled_without_rounding(self) -> None:
        response = self.post_raw_json(self.raw_callback("99.0036"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.apply.call_count, 1)
        self.logger.warning.assert_not_called()

    def test_raw_precise_underpayment_is_safe_mismatch_without_fulfilment(
        self,
    ) -> None:
        response = self.post_raw_json(
            self.raw_callback("98.999999999999999999"),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")
        self.apply.assert_not_called()
        self.logger.warning.assert_called_once_with(
            {
                "reason_code": "callback_mismatch",
                "intent_id": self.intent.pk,
                "provider_transaction_id": _TRANSACTION_ID,
            }
        )

    def test_raw_non_numeric_and_non_finite_amounts_are_empty_safe_200(
        self,
    ) -> None:
        amount_tokens = (
            '"99.00"',
            "true",
            "null",
            "[]",
            "{}",
            "NaN",
            "Infinity",
            "-Infinity",
        )
        validator = mock.Mock(
            return_value=ValidatePlategaCallbackOut(
                payment=None,
                reason_code="invalid_payload",
                warning=None,
            )
        )
        with mock.patch(
            f"{_VIEW}.get_validate_platega_callback_service",
            return_value=validator,
        ) as get_validator:
            for amount_token in amount_tokens:
                with self.subTest(amount_token=amount_token):
                    response = self.post_raw_json(
                        self.raw_callback(amount_token),
                    )

                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.content, b"")

            get_validator.assert_not_called()

        self.assert_no_domain_processing()

    def test_serializer_converts_direct_int_and_float_through_text(self) -> None:
        cases = (
            (99, Decimal("99")),
            (99.0036, Decimal("99.0036")),
        )
        for amount, expected in cases:
            with self.subTest(amount=amount):
                incoming = PlategaCallbackSerializer(
                    data=self.payload(amount=amount),
                )

                self.assertTrue(incoming.is_valid(), incoming.errors)
                self.assertEqual(incoming.validated_data["amount"], expected)

    def test_serializer_rejects_direct_non_numeric_and_non_finite_amounts(
        self,
    ) -> None:
        invalid_amounts = (
            "99.00",
            True,
            None,
            [],
            {},
            Decimal("NaN"),
            Decimal("Infinity"),
            float("nan"),
            float("inf"),
        )
        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                incoming = PlategaCallbackSerializer(
                    data=self.payload(amount=amount),
                )

                self.assertFalse(incoming.is_valid())
                self.assertIn("amount", incoming.errors)

    def test_serializer_maps_exact_provider_keys_to_callback_dto(self) -> None:
        validator = mock.Mock(
            return_value=ValidatePlategaCallbackOut(
                payment=None,
                reason_code="canceled",
                warning=None,
            )
        )
        with mock.patch(
            f"{_VIEW}.get_validate_platega_callback_service",
            return_value=validator,
        ):
            response = self.post_payload(self.payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        callback = validator.call_args.kwargs["callback"]
        self.assertEqual(callback.transaction_id, _TRANSACTION_ID)
        self.assertEqual(callback.amount, Decimal("99.00"))
        self.assertEqual(callback.currency, "RUB")
        self.assertEqual(callback.status, "CONFIRMED")
        self.assertEqual(callback.payment_method, 2)
        self.assert_no_domain_processing()

    def test_unknown_mismatch_and_unsupported_callbacks_log_only_allowlist(
        self,
    ) -> None:
        unknown_id = uuid4()
        cases = (
            (
                self.payload(id=str(unknown_id)),
                PlategaCallbackWarningDTO(
                    reason_code="unknown_transaction",
                    intent_id=None,
                    provider_transaction_id=unknown_id,
                ),
            ),
            (
                self.payload(amount=98.99),
                PlategaCallbackWarningDTO(
                    reason_code="callback_mismatch",
                    intent_id=self.intent.pk,
                    provider_transaction_id=_TRANSACTION_ID,
                ),
            ),
            (
                self.payload(status="CHARGEBACKED"),
                PlategaCallbackWarningDTO(
                    reason_code="unsupported_status",
                    intent_id=self.intent.pk,
                    provider_transaction_id=_TRANSACTION_ID,
                ),
            ),
        )
        for payload, expected_warning in cases:
            with self.subTest(reason=expected_warning.reason_code):
                response = self.post_payload(payload)

                expected = asdict(expected_warning)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.logger.warning.assert_called_once_with(expected)
                self.assertEqual(
                    set(self.logger.warning.call_args.args[0]),
                    {"reason_code", "intent_id", "provider_transaction_id"},
                )
                rendered = repr(self.logger.warning.call_args)
                for forbidden in (
                    _MERCHANT_ID,
                    _SECRET,
                    self.intent.initiator.username,
                    self.intent.provider_payment_url,
                    "paymentMethod",
                    "metadata",
                    "payload",
                ):
                    self.assertNotIn(forbidden, rendered)
                self.apply.assert_not_called()
                self.logger.reset_mock()

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PlategaPaymentIntentStatusEnum.ACTIVE)

    def test_matching_canceled_and_repeated_canceled_are_safe_200_without_warning(
        self,
    ) -> None:
        canceled = self.payload(status="CANCELED")

        first = self.post_payload(canceled)
        second = self.post_payload(canceled)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.intent.refresh_from_db()
        self.assertEqual(
            self.intent.status,
            PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
        )
        self.assert_no_domain_processing()

    def test_confirmed_fulfilment_and_duplicate_are_200(self) -> None:
        response = self.post_payload(self.payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = self.apply.call_args.kwargs["payment"]
        self.assertEqual(payment.intent_id, self.intent.pk)
        self.assertEqual(payment.transaction_id, _TRANSACTION_ID)
        self.logger.warning.assert_not_called()

        self.intent.status = PlategaPaymentIntentStatusEnum.FULFILLED
        self.intent.save(update_fields=["status"])
        self.apply.return_value = ApplyPlategaPaymentOut(
            fulfilled=False,
            already_fulfilled=True,
        )
        duplicate = self.post_payload(self.payload())

        self.assertEqual(duplicate.status_code, status.HTTP_200_OK)
        self.assertEqual(self.apply.call_count, 2)
        self.logger.warning.assert_not_called()

    def test_validator_and_apply_retryable_failures_are_503(self) -> None:
        apply_errors = (
            PlategaPaymentRetryable("0", reason_code="processing"),
            PlategaPaymentRetryable("0", reason_code="fulfillment_retryable"),
        )
        for error in apply_errors:
            with self.subTest(reason=error.context["reason_code"]):
                self.apply.side_effect = error
                response = self.post_payload(self.payload())
                self.assertEqual(
                    response.status_code,
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                )
                self.apply.reset_mock(side_effect=True)

        with mock.patch(
            f"{_VIEW}.get_validate_platega_callback_service"
        ) as get_validator:
            get_validator.return_value.side_effect = OperationalError(
                "database unavailable"
            )
            response = self.post_payload(self.payload())

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.logger.warning.assert_not_called()

    @mock.patch("requests.get")
    def test_callback_never_queries_provider_status(self, provider_get: mock.Mock) -> None:
        response = self.post_payload(self.payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        provider_get.assert_not_called()
