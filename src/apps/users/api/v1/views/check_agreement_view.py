from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta
from apps.users.api.v1.serializers import CheckAgreementSerializer
from apps.users.models import SystemUser
from apps.users.permissions import BotAuthToken
from apps.vds.models import MTPRotoKey


class UserAgreementView(APIView):
    permission_classes = (BotAuthToken,)

    def post(self, request: Request) -> Response:
        serializer = CheckAgreementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = SystemUser.objects.get(username=serializer.validated_data["username"])
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(username=serializer.validated_data["username"])

        user.is_agree = serializer.validated_data["is_agree"]
        user.save(update_fields=["is_agree"])

        link = MTPRotoKey.objects.filter(user__username=serializer.validated_data["username"]).first()
        link.is_winner = True
        link.expired_date = (link.expired_date + timedelta(days=365))
        link.save(update_fields=["is_winner", "expired_date"])

        return Response(data={"link": link.get_proxy_link()}, status=status.HTTP_201_CREATED)
