from __future__ import annotations

from rest_framework import serializers


class FirstFreeLinkSerializer(serializers.Serializer):
    username = serializers.CharField()


class CheckFirstFreeLinkSerializer(serializers.Serializer):
    username = serializers.CharField()
    telegram_username = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    invited_from_username = serializers.CharField(default=None)


class LegalConsentStatusSerializer(serializers.Serializer):
    username = serializers.CharField()


class AcceptLegalConsentSerializer(serializers.Serializer):
    username = serializers.CharField()
    telegram_username = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    invited_from_username = serializers.CharField(required=False, default=None)
