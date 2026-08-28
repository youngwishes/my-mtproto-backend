from rest_framework import serializers


class ReferralCabinetSerializer(serializers.Serializer):
    username = serializers.CharField()
