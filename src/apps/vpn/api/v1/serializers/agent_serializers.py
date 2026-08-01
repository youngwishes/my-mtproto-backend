from __future__ import annotations

from rest_framework import serializers


class AgentProfileSerializer(serializers.Serializer):
    access_id = serializers.IntegerField()
    vless_uuid = serializers.UUIDField()
    hysteria_secret = serializers.CharField()
