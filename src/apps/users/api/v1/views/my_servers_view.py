from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.v1.serializers import MyServersSerializer
from apps.users.permissions import BotAuthToken
from apps.vds.services import get_my_servers_service


class MyServersView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = MyServersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_my_servers_service()
        result = service(username=serializer.validated_data["username"])
        return Response(result.asdict(), status=status.HTTP_200_OK)
