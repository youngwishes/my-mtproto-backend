from __future__ import annotations

from rest_framework import serializers


class VPNMenuSerializer(serializers.Serializer):
    username = serializers.CharField()
