from __future__ import annotations

from rest_framework import serializers


class ReissueVPNSubscriptionSerializer(serializers.Serializer):
    username = serializers.CharField()
