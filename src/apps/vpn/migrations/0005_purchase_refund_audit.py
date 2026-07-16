from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vpn", "0004_access_first_ready_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="vpnpurchase",
            name="refund_reason",
            field=models.CharField(
                blank=True,
                max_length=128,
                null=True,
                verbose_name="причина возврата",
            ),
        ),
        migrations.AddField(
            model_name="vpnpurchase",
            name="refunded_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="возврат подтверждён"
            ),
        ),
        migrations.AddField(
            model_name="vpnpurchase",
            name="refunded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vpn_purchases_refunded",
                to="users.systemuser",
                verbose_name="возврат подтвердил",
            ),
        ),
        migrations.AddConstraint(
            model_name="vpnpurchase",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        refunded_at__isnull=True,
                        refunded_by__isnull=True,
                        refund_reason__isnull=True,
                    )
                    | (
                        models.Q(
                            refunded_at__isnull=False,
                            refunded_by__isnull=False,
                            refund_reason__isnull=False,
                        )
                        & ~models.Q(refund_reason="")
                    )
                ),
                name="vpn_purchase_refund_audit_complete",
            ),
        ),
    ]
