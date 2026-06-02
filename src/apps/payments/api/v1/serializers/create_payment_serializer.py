from rest_framework import serializers

from apps.payments.enums import PaymentProviderEnum


class CreatePaymentSerializer(serializers.Serializer):
    username = serializers.CharField()
    charge_id = serializers.CharField(allow_blank=True)
    provider = serializers.ChoiceField(choices=PaymentProviderEnum.choices())
