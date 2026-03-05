from rest_framework import serializers


class FirstFreeLinkSerializer(serializers.Serializer):
    username = serializers.CharField()


class CheckFirstFreeLinkSerializer(serializers.Serializer):
    username = serializers.CharField()
    telegram_username = serializers.CharField(required=False)
