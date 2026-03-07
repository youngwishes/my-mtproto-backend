from rest_framework import serializers


class CreatePaymentSerializer(serializers.Serializer):
    username = serializers.CharField()
