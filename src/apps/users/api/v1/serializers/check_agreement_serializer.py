from rest_framework import serializers


class CheckAgreementSerializer(serializers.Serializer):
    username = serializers.CharField()
    is_agree = serializers.BooleanField()
