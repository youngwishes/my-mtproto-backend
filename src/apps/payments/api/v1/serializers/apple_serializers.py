from __future__ import annotations

from rest_framework import serializers

from apps.payments.enums import AppleRedemptionModeEnum


class ApplePurchaseOutcomeSerializer(serializers.Serializer):
    """Serialize a backend-saved apple cashback purchase outcome."""

    apples_earned = serializers.IntegerField(read_only=True)
    rate_percent = serializers.IntegerField(read_only=True)
    balance = serializers.IntegerField(read_only=True)
    eligible_purchase_count = serializers.IntegerField(read_only=True)
    level = serializers.CharField(read_only=True)
    level_up = serializers.BooleanField(read_only=True)
    next_purchase_rate_percent = serializers.IntegerField(read_only=True)


def reject_unknown_fields(
    *, serializer: serializers.Serializer, data: object
) -> None:
    """Reject client-owned values outside an exact bot-facing contract."""

    if isinstance(data, dict):
        unknown = set(data) - set(serializer.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: ["Unexpected field."] for field in sorted(unknown)}
            )


class _ExactInputSerializer(serializers.Serializer):
    def to_internal_value(self, data: object) -> dict:
        reject_unknown_fields(serializer=self, data=data)
        return super().to_internal_value(data)


class AppleStatusRequestSerializer(_ExactInputSerializer):
    """Validate the sole user identifier accepted by apple status."""

    username = serializers.CharField()


class AppleStatusResponseSerializer(serializers.Serializer):
    """Serialize backend-derived balance, level and redemption readiness."""

    balance = serializers.IntegerField(read_only=True)
    eligible_purchase_count = serializers.IntegerField(read_only=True)
    level = serializers.CharField(read_only=True)
    rate_percent = serializers.IntegerField(read_only=True)
    next_level_purchase_count = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    purchases_to_next_level = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    is_max_level = serializers.BooleanField(read_only=True)
    redeemable_days = serializers.IntegerField(read_only=True)
    missing_apples = serializers.IntegerField(read_only=True)
    has_existing_key = serializers.BooleanField(read_only=True)


class AppleRedemptionPreviewRequestSerializer(_ExactInputSerializer):
    """Validate an authoritative one-day or all-apples quote request."""

    username = serializers.CharField()
    mode = serializers.ChoiceField(
        choices=(
            AppleRedemptionModeEnum.ONE_DAY,
            AppleRedemptionModeEnum.ALL,
        )
    )


class AppleRedemptionPreviewResponseSerializer(serializers.Serializer):
    """Serialize the immutable redemption quote saved by the backend."""

    confirmation_id = serializers.IntegerField(read_only=True)
    mode = serializers.CharField(read_only=True)
    apples_spent = serializers.IntegerField(read_only=True)
    days = serializers.IntegerField(read_only=True)
    projected_expired_date = serializers.CharField(read_only=True)


class AppleRedemptionConfirmRequestSerializer(_ExactInputSerializer):
    """Validate a confirmation using only its owner and saved quote ID."""

    username = serializers.CharField()
    confirmation_id = serializers.IntegerField(min_value=1)


class AppleRedemptionConfirmResponseSerializer(serializers.Serializer):
    """Serialize the committed apple debit and MTProxy expiry."""

    apples_spent = serializers.IntegerField(read_only=True)
    days = serializers.IntegerField(read_only=True)
    expired_date = serializers.CharField(read_only=True)
    balance = serializers.IntegerField(read_only=True)
