from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class GetProductSerializer(serializers.Serializer):
    payment_methods = serializers.SerializerMethodField()
    priority_payment_methods = serializers.SerializerMethodField()
    rub_amount = serializers.SerializerMethodField()
    title = serializers.CharField()
    description = serializers.CharField()
    currency = serializers.CharField()
    provider_data = serializers.JSONField(source="provider_data_json")
    send_email_to_provider = serializers.BooleanField()
    need_email = serializers.BooleanField()
    price = serializers.FloatField()
    stars_price = serializers.IntegerField()

    def get_payment_methods(self, obj: object) -> tuple[str, ...]:
        return tuple(self.context["payment_methods"])

    def get_priority_payment_methods(self, obj: object) -> tuple[str, ...]:
        return tuple(self.context["priority_payment_methods"])

    def get_rub_amount(self, obj: object) -> str:
        price = Decimal(obj.price)
        return format((price / Decimal("100")).quantize(Decimal("0.01")), ".2f")
