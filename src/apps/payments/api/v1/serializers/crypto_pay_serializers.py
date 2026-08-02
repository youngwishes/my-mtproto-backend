from __future__ import annotations

from rest_framework import serializers

from apps.payments.enums import PaymentKindEnum


class CreateCryptoInvoiceRequestSerializer(serializers.Serializer):
    """Validate the fixed bot-to-backend Crypto invoice request."""

    username = serializers.CharField()
    purchase_kind = serializers.ChoiceField(choices=PaymentKindEnum.choices())


class CreateCryptoInvoiceResponseSerializer(serializers.Serializer):
    """Serialize the exact decimal-safe create/reuse response."""

    invoice_url = serializers.URLField()
    rub_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=True,
    )
    expires_at = serializers.DateTimeField()
    reused = serializers.BooleanField()
