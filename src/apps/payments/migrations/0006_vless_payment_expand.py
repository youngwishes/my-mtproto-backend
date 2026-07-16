from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count


def backfill_legacy_product(apps, schema_editor) -> None:
    product = apps.get_model("payments", "Product")
    payment = apps.get_model("payments", "Payment")
    database_alias = schema_editor.connection.alias

    active_products = list(
        product.objects.using(database_alias)
        .filter(is_active=True)
        .values_list("pk", flat=True)
    )
    if len(active_products) > 1:
        raise RuntimeError("VLESS expand migration requires exactly one active Product")

    duplicate_identity_exists = (
        payment.objects.using(database_alias)
        .exclude(charge_id="")
        .values("provider", "charge_id")
        .annotate(identity_count=Count("pk"))
        .filter(identity_count__gt=1)
        .exists()
    )
    if duplicate_identity_exists:
        raise RuntimeError("VLESS expand migration found duplicate payment identities")

    if not active_products:
        return

    product_pk = active_products[0]
    product.objects.using(database_alias).filter(pk=product_pk).update(
        code="mtproto_30d"
    )
    payment.objects.using(database_alias).filter(product__isnull=True).update(
        product_id=product_pk
    )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0005_gift_certificates"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("mtproto_30d", "MTProto, 30 дней"),
                    ("vless_30d", "VLESS, 30 дней"),
                ],
                max_length=32,
                null=True,
                verbose_name="стабильный код",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="payments.product",
                verbose_name="товар",
            ),
        ),
        migrations.RunPython(backfill_legacy_product, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="payment",
            name="uniq_gift_certificate_payment_identity",
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                condition=models.Q(("code__isnull", False), ~models.Q(("code", ""))),
                fields=("code",),
                name="uniq_non_empty_product_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=~models.Q(("charge_id", "")),
                fields=("provider", "charge_id"),
                name="uniq_non_empty_payment_identity",
            ),
        ),
    ]
