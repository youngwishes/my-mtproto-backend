from __future__ import annotations

from rest_framework import serializers


class VPNSubscriptionTokenSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=43, max_length=128, trim_whitespace=False)
