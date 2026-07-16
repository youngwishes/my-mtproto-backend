from __future__ import annotations

from typing import ClassVar

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    MethodNotAllowed,
    NotAuthenticated,
    ParseError,
    PermissionDenied,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BaseServiceError
from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.exceptions import (
    BadPaymentData,
    PaymentIdentityConflict,
    PaymentIntentExpired,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
    VPNProductNotConfigured,
)
from apps.payments.services.dtos import (
    AcceptPaymentReceiptIn,
    CreatePaymentIntentIn,
    PreCheckoutPaymentIntentIn,
)
from apps.users.permissions import BotAuthToken
from apps.vpn.api.v1.serializers import (
    VPNPaymentIntentSerializer,
    VPNPreCheckoutSerializer,
    VPNSuccessfulPaymentSerializer,
    VPNUsernameSerializer,
)
from apps.vpn.exceptions import (
    VPNAccessExpired,
    VPNAccessNotFound,
    VPNCapacityUnavailable,
    VPNReissueConflict,
    VPNReissueInProgress,
    VPNReissueNotEligible,
    VPNSalesDisabled,
)
from apps.vpn.factories import (
    get_accept_vpn_payment_receipt_service,
    get_approve_vpn_payment_intent_service,
    get_create_vpn_payment_intent_service,
    get_reissue_vpn_access_by_username_service,
    get_vpn_access_status_service,
)


class VPNBotAPIView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    error_contracts: ClassVar[dict[type[BaseServiceError], tuple[int, str, str]]] = {
        BadPaymentData: (400, "bad_payment_data", "Некорректные данные платежа"),
        VPNProductNotConfigured: (
            404,
            "vpn_product_not_configured",
            "VPN-продукт временно недоступен",
        ),
        VPNSalesDisabled: (
            409,
            "vpn_sales_disabled",
            "Продажи VPN временно приостановлены",
        ),
        VPNCapacityUnavailable: (
            503,
            "vpn_capacity_unavailable",
            "Сейчас нет доступных VPN-серверов",
        ),
        PaymentIntentNotFound: (
            404,
            "payment_intent_not_found",
            "Намерение платежа не найдено",
        ),
        PaymentIntentMismatch: (
            409,
            "payment_intent_mismatch",
            "Данные платежа не совпадают с выставленным счётом",
        ),
        PaymentIntentExpired: (
            409,
            "payment_intent_expired",
            "Срок действия счёта истёк",
        ),
        PaymentIdentityConflict: (
            409,
            "payment_identity_conflict",
            "Идентификатор платежа уже связан с другими данными",
        ),
        VPNAccessNotFound: (404, "vpn_access_not_found", "VPN-доступ не найден"),
        VPNAccessExpired: (
            409,
            "vpn_access_expired",
            "Срок VPN-доступа истёк",
        ),
        VPNReissueInProgress: (
            409,
            "vpn_reissue_in_progress",
            "Перевыпуск VPN-доступа уже выполняется",
        ),
        VPNReissueConflict: (
            409,
            "vpn_reissue_in_progress",
            "Перевыпуск VPN-доступа уже выполняется",
        ),
        VPNReissueNotEligible: (
            409,
            "vpn_reissue_in_progress",
            "Перевыпуск VPN-доступа уже выполняется",
        ),
    }

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, (ParseError, UnsupportedMediaType, ValidationError)):
            return self._error(
                status_code=400,
                code="bad_payment_data",
                message="Некорректные данные платежа",
            )
        if isinstance(exc, (NotAuthenticated, PermissionDenied)):
            return self._error(
                status_code=403,
                code="forbidden",
                message="Доступ запрещён",
            )
        if isinstance(exc, MethodNotAllowed):
            return self._error(
                status_code=405,
                code="method_not_allowed",
                message="Метод не поддерживается",
            )
        for exception_type, contract in self.error_contracts.items():
            if isinstance(exc, exception_type):
                status_code, code, message = contract
                return self._error(
                    status_code=status_code,
                    code=code,
                    message=message,
                )
        if isinstance(exc, APIException):
            return self._error(
                status_code=exc.status_code,
                code="api_error",
                message="Ошибка API",
            )
        return self._error(
            status_code=500,
            code="internal_error",
            message="Временная внутренняя ошибка",
        )

    def _error(self, *, status_code: int, code: str, message: str) -> Response:
        return Response(
            data={"code": code, "message": message, "detail": {}},
            status=status_code,
        )


class VPNPaymentIntentView(VPNBotAPIView):
    def post(self, request: Request) -> Response:
        serializer = VPNPaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_create_vpn_payment_intent_service()(
            intent=CreatePaymentIntentIn(**serializer.validated_data),
        )
        data: dict[str, object] = {
            "title": result.title,
            "description": result.description,
            "invoice_payload": result.invoice_payload,
            "currency": result.currency,
            "provider": result.provider,
            "expires_at": result.expires_at,
        }
        if result.currency == "RUB":
            data.update(
                {
                    "provider_data": result.provider_data,
                    "send_email_to_provider": result.send_email_to_provider,
                    "need_email": result.need_email,
                    "price": result.amount,
                }
            )
        else:
            data["stars_price"] = result.amount
        return Response(data=data, status=status.HTTP_200_OK)


class VPNPreCheckoutView(VPNBotAPIView):
    def post(self, request: Request) -> Response:
        serializer = VPNPreCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        get_approve_vpn_payment_intent_service()(
            pre_checkout=PreCheckoutPaymentIntentIn(**serializer.validated_data),
        )
        return Response(data={"status": "APPROVED"}, status=status.HTTP_200_OK)


class VPNSuccessfulPaymentView(VPNBotAPIView):
    def post(self, request: Request) -> Response:
        serializer = VPNSuccessfulPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_accept_vpn_payment_receipt_service()(
            payment=AcceptPaymentReceiptIn(**serializer.validated_data),
        )
        if result.status == PaymentReceiptStatusEnum.APPLIED:
            return Response(data={"status": "APPLIED"}, status=status.HTTP_200_OK)
        return Response(data={"status": "ACCEPTED"}, status=status.HTTP_202_ACCEPTED)


class VPNStatusView(VPNBotAPIView):
    def post(self, request: Request) -> Response:
        serializer = VPNUsernameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_vpn_access_status_service()(
            username=serializer.validated_data["username"],
        )
        data: dict[str, object] = {"status": result.status}
        if result.expired_at is not None:
            data["expired_at"] = result.expired_at
        if result.status == "READY" and result.subscription_url is not None:
            data["subscription_url"] = result.subscription_url
        return Response(data=data, status=status.HTTP_200_OK)


class VPNReissueView(VPNBotAPIView):
    def post(self, request: Request) -> Response:
        serializer = VPNUsernameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        get_reissue_vpn_access_by_username_service()(
            username=serializer.validated_data["username"],
        )
        return Response(
            data={"status": "PREPARING"},
            status=status.HTTP_202_ACCEPTED,
        )
