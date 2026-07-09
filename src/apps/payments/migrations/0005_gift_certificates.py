from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0004_alter_product_stars_price"),
        ("users", "0008_systemuser_referral_link_activated_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="kind",
            field=models.CharField(
                choices=[
                    ("subscription", "Подписка"),
                    ("gift_certificate", "Подарочный сертификат"),
                ],
                default="subscription",
                max_length=32,
                verbose_name="тип платежа",
            ),
        ),
        migrations.CreateModel(
            name="GiftCertificate",
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
                        null=True,
                        auto_now_add=True,
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
                ("code", models.CharField(max_length=13, unique=True, verbose_name="код")),
                ("expires_at", models.DateTimeField(verbose_name="действует до")),
                (
                    "activated_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="дата активации",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Создан"),
                            ("activated", "Активирован"),
                            ("expired", "Истёк"),
                        ],
                        default="created",
                        max_length=16,
                        verbose_name="статус",
                    ),
                ),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gift_certificates_activated",
                        to="users.systemuser",
                        verbose_name="активировал",
                    ),
                ),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gift_certificates_bought",
                        to="users.systemuser",
                        verbose_name="покупатель",
                    ),
                ),
                (
                    "payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gift_certificate",
                        to="payments.payment",
                        verbose_name="платёж",
                    ),
                ),
            ],
            options={
                "verbose_name": "подарочный сертификат",
                "verbose_name_plural": "подарочные сертификаты",
            },
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=models.Q(kind="gift_certificate"),
                fields=("provider", "charge_id", "kind"),
                name="uniq_gift_certificate_payment_identity",
            ),
        ),
    ]
