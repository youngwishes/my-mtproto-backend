from __future__ import annotations

from rest_framework import serializers


class FortuneWheelStatusResponseSerializer(serializers.Serializer):
    registered = serializers.BooleanField()
    can_spin = serializers.BooleanField()
    last_prize = serializers.IntegerField(allow_null=True)
    next_spin_at = serializers.DateTimeField(allow_null=True)
    registration_url = serializers.URLField(allow_null=True)


class FortuneWheelSpinResponseSerializer(serializers.Serializer):
    prize_apples = serializers.IntegerField()
    spun_at = serializers.DateTimeField()
    next_spin_at = serializers.DateTimeField()


class FortuneWheelCooldownResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    last_prize = serializers.IntegerField()
    next_spin_at = serializers.DateTimeField()
