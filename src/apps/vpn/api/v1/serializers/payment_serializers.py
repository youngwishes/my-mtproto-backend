from __future__ import annotations

from rest_framework import serializers

from apps.payments.enums import PaymentProviderEnum, ProductCodeEnum


class FulfillVPNPaymentSerializer(serializers.Serializer):
    username = serializers.CharField()
    charge_id = serializers.CharField(allow_blank=False)
    provider = serializers.ChoiceField(choices=PaymentProviderEnum.choices())
    product_code = serializers.ChoiceField(choices=[ProductCodeEnum.VPN_30D])

    def validate(self, attrs: dict) -> dict:
        expected_fields = {"username", "charge_id", "provider", "product_code"}
        if set(self.initial_data) != expected_fields:
            raise serializers.ValidationError("Тело запроса содержит недопустимые поля.")
        return attrs
