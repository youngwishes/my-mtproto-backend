from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def seed_platega_commission(apps, schema_editor) -> None:
    payment_method = apps.get_model("payments", "PaymentMethod")
    platega, _ = payment_method.objects.get_or_create(
        code="platega_sbp",
        defaults={
            "is_active": False,
            "commission_percent": Decimal("8.00"),
        },
    )
    payment_method.objects.filter(pk=platega.pk).update(
        commission_percent=Decimal("8.00")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0009_platega_payment_intent"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="commission_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=5,
                validators=(
                    MinValueValidator(Decimal("0.00")),
                    MaxValueValidator(Decimal("999.99")),
                ),
                verbose_name="комиссия, %",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentmethod",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    commission_percent__gte=Decimal("0.00"),
                    commission_percent__lte=Decimal("999.99"),
                ),
                name="payment_method_commission_percent_range",
            ),
        ),
        migrations.RunPython(
            seed_platega_commission,
            migrations.RunPython.noop,
        ),
    ]
