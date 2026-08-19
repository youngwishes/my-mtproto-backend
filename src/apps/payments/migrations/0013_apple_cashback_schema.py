from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0012_paymentmethod_is_priority"),
        ("users", "0018_systemuser_apple_balance"),
        ("vds", "0021_hosting_vdsinstance_expired_at_vdsinstance_hosting"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppleCashbackPurchase",
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
                        auto_now_add=True, null=True, verbose_name="дата создания"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, null=True, verbose_name="дата обновления"
                    ),
                ),
                ("identity_key", models.CharField(max_length=256, unique=True, verbose_name="ключ идентичности")),
                ("rate_percent", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="ставка cashback, %")),
                ("apples_earned", models.PositiveIntegerField(verbose_name="начислено яблок")),
                ("balance_after", models.PositiveIntegerField(verbose_name="баланс после")),
                ("eligible_purchase_count_after", models.PositiveIntegerField(verbose_name="количество подходящих покупок после")),
                ("result_expired_at", models.DateTimeField(blank=True, null=True, verbose_name="результирующее истечение ключа")),
                (
                    "payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="apple_cashback_purchase",
                        to="payments.payment",
                        verbose_name="платёж",
                    ),
                ),
            ],
            options={
                "verbose_name": "покупка с apple cashback",
                "verbose_name_plural": "покупки с apple cashback",
            },
        ),
        migrations.CreateModel(
            name="AppleRedemption",
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
                        auto_now_add=True, null=True, verbose_name="дата создания"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, null=True, verbose_name="дата обновления"
                    ),
                ),
                ("apples_spent", models.PositiveIntegerField(verbose_name="потрачено яблок")),
                ("quoted_expired_at", models.DateTimeField(verbose_name="истечение из предпросмотра")),
                ("new_expired_at", models.DateTimeField(blank=True, null=True, verbose_name="новое истечение")),
                ("balance_after", models.PositiveIntegerField(blank=True, null=True, verbose_name="баланс после")),
                (
                    "key",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="apple_redemptions",
                        to="vds.mtprotokey",
                        verbose_name="ключ",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="apple_redemptions",
                        to="users.systemuser",
                        verbose_name="пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "списание яблок",
                "verbose_name_plural": "списания яблок",
            },
        ),
    ]
