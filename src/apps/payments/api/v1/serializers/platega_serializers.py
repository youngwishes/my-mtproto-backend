from __future__ import annotations

from collections.abc import Mapping

from rest_framework import serializers

from apps.payments.enums import PaymentKindEnum


class CreatePlategaInvoiceRequestSerializer(serializers.Serializer):
    """Validate the fixed bot-to-backend Platega create request."""

    username = serializers.CharField()
    purchase_kind = serializers.ChoiceField(choices=PaymentKindEnum.choices())


class CreatePlategaInvoiceResponseSerializer(serializers.Serializer):
    """Serialize the exact safe Platega create/reuse response."""

    payment_url = serializers.URLField()
    rub_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=True,
    )
    expires_at = serializers.DateTimeField()
    reused = serializers.BooleanField()


class PlategaCallbackSerializer(serializers.Serializer):
    """Normalize the exact authenticated Platega callback payload."""

    id = serializers.UUIDField(source="transaction_id")
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    paymentMethod = serializers.IntegerField(source="payment_method")

    def to_internal_value(self, data: object) -> dict[str, object]:
        expected_keys = {"id", "amount", "currency", "status", "paymentMethod"}
        if not isinstance(data, Mapping) or set(data) != expected_keys:
            raise serializers.ValidationError("Expected exact callback fields.")
        return super().to_internal_value(data)
