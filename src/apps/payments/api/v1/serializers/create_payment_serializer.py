from __future__ import annotations

from rest_framework import serializers

from apps.payments.api.v1.serializers.apple_serializers import (
    ApplePurchaseOutcomeSerializer,
    reject_unknown_fields,
)
from apps.payments.enums import PaymentProviderEnum


class CreatePaymentSerializer(serializers.Serializer):
    username = serializers.CharField()
    charge_id = serializers.CharField(allow_blank=False)
    provider = serializers.ChoiceField(choices=PaymentProviderEnum.choices())

    def to_internal_value(self, data: object) -> dict:
        reject_unknown_fields(serializer=self, data=data)
        return super().to_internal_value(data)


class CreatePaymentResponseSerializer(serializers.Serializer):
    """Serialize the saved normal subscription and loyalty result."""

    expired_date = serializers.CharField(read_only=True)
    loyalty = ApplePurchaseOutcomeSerializer(read_only=True)
