from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from unittest import mock
from uuid import UUID, uuid4

from django.db import OperationalError
from django.test import override_settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APITestCase

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
            "amount": "99.00",
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
                mock.call("wrong-merchant", _MERCHANT_ID),
                mock.call(_SECRET, _SECRET),
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
                self.payload(amount="98.99"),
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
