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


class _AcceptedAssetsField(serializers.CharField):
    def to_internal_value(self, data: object) -> frozenset[str]:
        value = super().to_internal_value(data)
        return frozenset(value.split(","))


class CryptoWebhookInvoiceSerializer(serializers.Serializer):
    """Parse the complete signed invoice payload into normalized DTO fields."""

    invoice_id = serializers.IntegerField()
    status = serializers.CharField()
    currency_type = serializers.CharField()
    fiat = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    accepted_assets = _AcceptedAssetsField()
    paid_asset = serializers.CharField(allow_null=True)
    payload = serializers.CharField()
    bot_invoice_url = serializers.URLField()
    created_at = serializers.DateTimeField()
    expiration_date = serializers.DateTimeField()
    paid_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


class CryptoWebhookSerializer(serializers.Serializer):
    """Parse a signed Crypto Pay event without performing authentication."""

    update_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    update_type = serializers.CharField()
    payload = CryptoWebhookInvoiceSerializer()
