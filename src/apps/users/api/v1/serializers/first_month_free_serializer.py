from rest_framework import serializers


class FirstMonthFreeSerializer(serializers.Serializer):
    username = serializers.CharField()
