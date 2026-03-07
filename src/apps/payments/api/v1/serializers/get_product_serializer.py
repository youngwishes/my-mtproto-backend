from rest_framework import serializers


class GetProductSerializer(serializers.Serializer):
    title = serializers.CharField()
    description = serializers.CharField()
    currency = serializers.CharField()
    provider_data = serializers.JSONField(source="provider_data_json")
    send_email_to_provider = serializers.BooleanField()
    need_email = serializers.BooleanField()
    price = serializers.FloatField()
