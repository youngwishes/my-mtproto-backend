from rest_framework import serializers


class FirstMonthFreeSerializer(serializers.Serializer):
    username = serializers.CharField()


class CheckFirstMonthFreeSerializer(serializers.Serializer):
    username = serializers.CharField()
    telegram_username = serializers.CharField(required=False)
