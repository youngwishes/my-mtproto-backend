from rest_framework import serializers


class Payload(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    amount = serializers.IntegerField()
    currency = serializers.CharField()
    user_id = serializers.CharField()
    telegram_user_id = serializers.CharField()
    purchase_id = serializers.CharField()
    transaction_id = serializers.CharField()
    purchase_created_at = serializers.DateTimeField()


class TributeDigitalPaymentSerializer(serializers.Serializer):
    name = serializers.CharField()
    created_at = serializers.DateTimeField()
    sent_at = serializers.DateTimeField()
    payload = Payload()
