from __future__ import annotations

from collections import defaultdict

from django.db import migrations


ELIGIBLE_PAYMENT_KINDS = ("subscription", "gift_certificate")


def _build_identity_key(*, provider: str, charge_id: str, kind: str) -> str:
    return f"{provider}:{charge_id}:{kind}"


def backfill_apple_cashback_purchases(apps, schema_editor) -> None:
    """Create zero-apple historical rows for unique eligible payments in time order."""
    payment_model = apps.get_model("payments", "Payment")
    purchase_model = apps.get_model("payments", "AppleCashbackPurchase")
    seen_identity_keys: set[str] = set()
    eligible_counts: dict[int, int] = defaultdict(int)

    payments = payment_model.objects.filter(
        kind__in=ELIGIBLE_PAYMENT_KINDS
    ).order_by("created_at", "pk")
    for payment in payments.iterator():
        if payment.charge_id:
            identity_key = _build_identity_key(
                provider=payment.provider,
                charge_id=payment.charge_id,
                kind=payment.kind,
            )
            if identity_key in seen_identity_keys:
                continue
            seen_identity_keys.add(identity_key)
        else:
            identity_key = f"legacy:{payment.pk}"

        eligible_counts[payment.user_id] += 1
        purchase_model.objects.create(
            payment_id=payment.pk,
            identity_key=identity_key,
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=eligible_counts[payment.user_id],
            result_expired_at=None,
        )


def remove_historical_apple_cashback_purchases(apps, schema_editor) -> None:
    """Remove only rows whose nullable snapshots identify launch history."""
    purchase_model = apps.get_model("payments", "AppleCashbackPurchase")
    purchase_model.objects.filter(
        rate_percent__isnull=True,
        result_expired_at__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0013_apple_cashback_schema"),
    ]

    operations = [
        migrations.RunPython(
            backfill_apple_cashback_purchases,
            remove_historical_apple_cashback_purchases,
        ),
    ]
