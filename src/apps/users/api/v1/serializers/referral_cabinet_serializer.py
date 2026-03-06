from rest_framework import serializers


class ReferralCabinetSerializer(serializers.Serializer):
    username = serializers.CharField()


class GetReferralLinkSerializer(serializers.Serializer):
    username = serializers.CharField()

