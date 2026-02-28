from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.bot import notify_bad_request
from apps.users.api.v1.serializers import FirstMonthFreeSerializer
from apps.users.permissions import BotAuthToken
from apps.users.services import get_first_month_free_service
from apps.users.services.check_first_month_free_service import (
    get_check_first_month_free_service,
)


class CreateFirstMonthFreeView(APIView):
    permission_classes = (BotAuthToken,)

    @notify_bad_request
    def post(self, request: Request) -> Response:
        serializer = FirstMonthFreeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_first_month_free_service()
        result = service(username=serializer.validated_data["username"])

        return Response(data=result, status=status.HTTP_200_OK)


class CheckFirstMonthFreeView(APIView):
    permission_classes = (BotAuthToken,)

    @notify_bad_request
    def post(self, request: Request) -> Response:
        serializer = FirstMonthFreeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_check_first_month_free_service()
        first_month_free_used = service(username=serializer.validated_data["username"])
        return Response(
            data={"has_access_for_free": first_month_free_used},
            status=status.HTTP_200_OK,
        )
