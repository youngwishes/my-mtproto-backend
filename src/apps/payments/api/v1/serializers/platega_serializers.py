from __future__ import annotations

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
