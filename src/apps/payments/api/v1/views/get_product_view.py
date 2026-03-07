from gunicorn.http import Request
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.api.v1.serializers import GetProductSerializer
from apps.payments.models import Product
from apps.users.permissions import BotAuthToken


class ProductAPIView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        serializer = GetProductSerializer(instance=Product.objects.active().first())
        return Response(data=serializer.data, status=status.HTTP_200_OK)
