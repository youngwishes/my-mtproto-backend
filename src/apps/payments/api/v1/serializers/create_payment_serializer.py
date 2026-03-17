from rest_framework import serializers


class CreatePaymentSerializer(serializers.Serializer):
    username = serializers.CharField()
    provider_payment_charge_id = serializers.CharField()
