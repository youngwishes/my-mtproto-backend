from __future__ import annotations

from typing import Any

from rest_framework import serializers


class _NumericStringField(serializers.CharField):
    default_error_messages = {
        "not_numeric_string": "Must be a string containing only ASCII digits.",
    }

    def to_internal_value(self, data: Any) -> str:
        if not isinstance(data, str):
            self.fail("not_numeric_string")

        value = super().to_internal_value(data)
        if not value.isascii() or not value.isdigit():
            self.fail("not_numeric_string")
        return value


class LegalConsentStatusSerializer(serializers.Serializer):
    username = _NumericStringField(trim_whitespace=False)


class AcceptLegalConsentSerializer(serializers.Serializer):
    username = _NumericStringField(trim_whitespace=False)
    telegram_username = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    invited_from_username = _NumericStringField(
        required=False,
        default=None,
        trim_whitespace=False,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        username = attrs["username"]
        invited_from_username = attrs.get("invited_from_username")
        if (
            invited_from_username is not None
            and (invited_from_username.lstrip("0") or "0")
            == (username.lstrip("0") or "0")
        ):
            raise serializers.ValidationError(
                {"invited_from_username": "Self-referral is not allowed."}
            )
        return attrs
