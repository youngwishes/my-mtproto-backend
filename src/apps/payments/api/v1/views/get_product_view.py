from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import GetProductSerializer
from apps.payments.enums import ProductCodeEnum
from apps.payments.exceptions import ProductNotFound
from apps.payments.selectors import get_active_product_by_code
from apps.users.permissions import BotAuthToken


class ProductAPIView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        product = get_active_product_by_code(code=ProductCodeEnum.MTPROTO_30D)
        if product is None:
            raise ProductNotFound(telegram_id="system")
        serializer = GetProductSerializer(instance=product)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
