from __future__ import annotations

from django.db import migrations, models


def backfill_ready_at(apps, schema_editor) -> None:
    receipt_model = apps.get_model("payments", "PaymentReceipt")
    rows = receipt_model.objects.filter(
        status="applied",
        payment__vpn_purchase__access__state="ready",
        ready_at__isnull=True,
    ).select_related("payment__vpn_purchase__access")
    pending = []
    for receipt in rows.iterator(chunk_size=500):
        access = receipt.payment.vpn_purchase.access
        applied_at = receipt.applied_at or receipt.updated_at
        access_ready_at = access.first_ready_at or access.updated_at
        if applied_at is None or access_ready_at is None:
            continue
        receipt.ready_at = max(applied_at, access_ready_at)
        pending.append(receipt)
        if len(pending) == 500:
            receipt_model.objects.bulk_update(pending, ("ready_at",), batch_size=500)
            pending.clear()
    if pending:
        receipt_model.objects.bulk_update(pending, ("ready_at",), batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0008_receipt_applied_at"),
        ("vpn", "0004_access_first_ready_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentreceipt",
            name="ready_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="VPN-доступ готов",
            ),
        ),
        migrations.RunPython(backfill_ready_at, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="paymentreceipt",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(ready_at__isnull=True)
                    | models.Q(applied_at__isnull=True)
                    | models.Q(ready_at__gte=models.F("applied_at"))
                ),
                name="payment_receipt_ready_not_before_applied",
            ),
        ),
    ]
