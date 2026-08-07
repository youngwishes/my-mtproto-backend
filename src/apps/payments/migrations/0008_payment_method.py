from __future__ import annotations

from django.db import migrations, models


SUPPORTED_PAYMENT_METHODS = ("stars", "crypto_pay")


def seed_payment_methods(apps, schema_editor) -> None:
    payment_method = apps.get_model("payments", "PaymentMethod")
    for code in SUPPORTED_PAYMENT_METHODS:
        payment_method.objects.get_or_create(
            code=code,
            defaults={"is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0007_crypto_payment_intent"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="активность"),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        null=True,
                        verbose_name="дата создания",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        null=True,
                        verbose_name="дата обновления",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("stars", "Telegram Stars"),
                            ("crypto_pay", "Crypto Pay"),
                        ],
                        max_length=32,
                        unique=True,
                        verbose_name="код",
                    ),
                ),
            ],
        ),
        migrations.RunPython(seed_payment_methods, migrations.RunPython.noop),
    ]
