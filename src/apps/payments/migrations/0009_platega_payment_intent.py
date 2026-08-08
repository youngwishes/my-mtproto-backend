from __future__ import annotations

import uuid

from django.db import migrations, models
import django.db.models.deletion


def seed_platega_payment_method(apps, schema_editor) -> None:
    payment_method = apps.get_model("payments", "PaymentMethod")
    payment_method.objects.get_or_create(
        code="platega_sbp",
        defaults={"is_active": False},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0008_payment_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("yukassa", "ЮKassa"),
                    ("stars", "Telegram Stars"),
                    ("crypto_pay", "Crypto Pay"),
                    ("platega", "Platega"),
                ],
                default="yukassa",
                max_length=16,
                verbose_name="провайдер",
            ),
        ),
        migrations.AlterField(
            model_name="paymentmethod",
            name="code",
            field=models.CharField(
                choices=[
                    ("platega_sbp", "СБП"),
                    ("stars", "Telegram Stars"),
                    ("crypto_pay", "Crypto Pay"),
                ],
                max_length=32,
                unique=True,
                verbose_name="код",
            ),
        ),
        migrations.CreateModel(
            name="PlategaPaymentIntent",
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
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "purchase_kind",
                    models.CharField(
                        choices=[
                            ("subscription", "Подписка"),
                            ("vpn_subscription", "VPN-подписка"),
                            ("gift_certificate", "Подарочный сертификат"),
                        ],
                        max_length=32,
                    ),
                ),
                ("product_code", models.CharField(max_length=32)),
                ("rub_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="RUB", max_length=3)),
                ("payment_method", models.PositiveSmallIntegerField(default=2)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("creating", "creating"),
                            ("active", "active"),
                            ("local_expired", "local_expired"),
                            ("processing", "processing"),
                            ("retryable", "retryable"),
                            ("provider_canceled", "provider_canceled"),
                            ("create_failed", "create_failed"),
                            ("fulfilled", "fulfilled"),
                        ],
                        default="creating",
                        max_length=32,
                    ),
                ),
                (
                    "provider_transaction_id",
                    models.UUIDField(blank=True, null=True, unique=True),
                ),
                ("provider_payment_url", models.URLField(blank=True, max_length=512)),
                ("provider_expires_at", models.DateTimeField(blank=True, null=True)),
                ("fulfillment_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("notification_queued_at", models.DateTimeField(blank=True, null=True)),
                ("notification_sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                (
                    "initiator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platega_payment_intents",
                        to="users.systemuser",
                    ),
                ),
                (
                    "payment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platega_intent",
                        to="payments.payment",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status__in", ("creating", "active"))),
                        fields=("initiator", "purchase_kind"),
                        name="uniq_active_platega_intent_per_user_kind",
                    ),
                ],
            },
        ),
        migrations.RunPython(seed_platega_payment_method, migrations.RunPython.noop),
    ]
