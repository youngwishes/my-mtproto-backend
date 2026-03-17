from rest_framework import serializers


class UpdateKeySerializer(serializers.Serializer):
    username = serializers.CharField()
