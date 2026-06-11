from rest_framework import serializers


class MyServersSerializer(serializers.Serializer):
    username = serializers.CharField()
