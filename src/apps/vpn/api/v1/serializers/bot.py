from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from apps.payments.enums import PaymentProviderEnum


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {"non_field_errors": ("unknown fields",)}
                )
        return super().to_internal_value(data)


class VPNUsernameSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)


class VPNPaymentIntentSerializer(VPNUsernameSerializer):
    currency = serializers.ChoiceField(choices=("RUB", "XTR"))


class VPNPreCheckoutSerializer(VPNUsernameSerializer):
    invoice_payload = serializers.RegexField(r"\A[0-9a-f]{64}\Z")
    currency = serializers.ChoiceField(choices=("RUB", "XTR"))
    amount = serializers.IntegerField(min_value=1)


class VPNSuccessfulPaymentSerializer(VPNPreCheckoutSerializer):
    provider = serializers.ChoiceField(choices=PaymentProviderEnum.choices())
    charge_id = serializers.CharField(max_length=255, allow_blank=False)
