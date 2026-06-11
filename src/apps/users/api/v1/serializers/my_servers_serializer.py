from __future__ import annotations

from rest_framework import serializers


class MyServersSerializer(serializers.Serializer):
    username = serializers.CharField()
