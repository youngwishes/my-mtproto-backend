from __future__ import annotations

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0006_product_code_vpn_payment"),
        ("users", "0008_systemuser_referral_link_activated_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="CryptoPaymentIntent",
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
                ("is_active", models.BooleanField(default=True, verbose_name="активность")),
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("creating", "creating"),
                            ("active", "active"),
                            ("local_expired", "local_expired"),
                            ("processing", "processing"),
                            ("retryable", "retryable"),
                            ("fulfilled", "fulfilled"),
                            ("create_failed", "create_failed"),
                            ("provider_expired", "provider_expired"),
                        ],
                        default="creating",
                        max_length=32,
                    ),
                ),
                ("provider_invoice_id", models.PositiveBigIntegerField(blank=True, null=True, unique=True)),
                ("provider_invoice_url", models.URLField(blank=True, max_length=512)),
                ("provider_created_at", models.DateTimeField(blank=True, null=True)),
                ("provider_expires_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("fulfillment_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("notification_sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                (
                    "initiator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crypto_payment_intents",
                        to="users.systemuser",
                    ),
                ),
                (
                    "payment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crypto_intent",
                        to="payments.payment",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("yukassa", "ЮKassa"),
                    ("stars", "Telegram Stars"),
                    ("crypto_pay", "Crypto Pay"),
                ],
                default="yukassa",
                max_length=16,
                verbose_name="провайдер",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("provider", "crypto_pay")),
                fields=("provider", "charge_id", "kind"),
                name="uniq_crypto_payment_identity",
            ),
        ),
        migrations.AddConstraint(
            model_name="cryptopaymentintent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ("creating", "active"))),
                fields=("initiator", "purchase_kind"),
                name="uniq_active_crypto_intent_per_user_kind",
            ),
        ),
    ]
