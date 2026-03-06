from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.v1.serializers import ReferralCabinetSerializer
from apps.users.permissions import BotAuthToken
from apps.users.services import get_referral_cabinet_service, get_referral_vds_link_service


class ReferralCabinetView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = ReferralCabinetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_referral_cabinet_service()
        response = service(username=serializer.validated_data["username"])

        return Response(data=response.asdict(), status=status.HTTP_200_OK)



class GetReferralLinkView(APIView):
    permission_classes = (BotAuthToken,)
    http_method_names = ["post"]

    def post(self, request: Request) -> Response:
        serializer = ReferralCabinetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = get_referral_vds_link_service()
        response = service(username=serializer.validated_data["username"])

        return Response(data=response.asdict(), status=status.HTTP_200_OK)
