from __future__ import annotations

from rest_framework import serializers

from apps.payments.enums import PaymentProviderEnum


class CreateGiftCertificateSerializer(serializers.Serializer):
    username = serializers.CharField()
    charge_id = serializers.CharField(allow_blank=True)
    provider = serializers.ChoiceField(choices=PaymentProviderEnum.choices())


class ActivateGiftCertificateSerializer(serializers.Serializer):
    username = serializers.CharField()
    code = serializers.CharField()
