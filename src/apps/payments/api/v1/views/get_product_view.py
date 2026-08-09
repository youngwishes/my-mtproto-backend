from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import GetProductSerializer
from apps.payments.enums import ProductCodeEnum
from apps.payments.exceptions import ProductNotFound
from apps.payments.selectors import (
    get_active_payment_method_codes,
    get_active_priority_payment_method_codes,
    get_active_product_by_code,
)
from apps.users.permissions import BotAuthToken


class ProductAPIView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(
        self,
        request: Request,
        code: str = ProductCodeEnum.MTPROTO_30D,
    ) -> Response:
        product = get_active_product_by_code(code=code)
        if product is None:
            raise ProductNotFound(telegram_id="system")
        payment_methods = get_active_payment_method_codes()
        priority_codes = get_active_priority_payment_method_codes()
        priority_payment_methods = tuple(
            code for code in payment_methods if code in priority_codes
        )
        serializer = GetProductSerializer(
            instance=product,
            context={
                "payment_methods": payment_methods,
                "priority_payment_methods": priority_payment_methods,
            },
        )
        return Response(data=serializer.data, status=status.HTTP_200_OK)
