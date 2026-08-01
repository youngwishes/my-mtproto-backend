from __future__ import annotations

import json

from django.db import migrations, models


MTPROTO_30D = "mtproto_30d"
VPN_30D = "vpn_30d"


def add_product_codes_and_vpn_product(apps, schema_editor) -> None:
    product_model = apps.get_model("payments", "Product")
    existing_product = product_model.objects.order_by("pk").first()
    if existing_product is not None:
        existing_product.code = MTPROTO_30D
        existing_product.save(update_fields=["code"])

    product_model.objects.create(
        code=VPN_30D,
        title="VPN на 30 дней",
        description="VPN-подписка на 30 дней.",
        provider_data=json.dumps(
            {
                "receipt": {
                    "customer": {},
                    "items": [
                        {
                            "description": "Оплата VPN-подписки на один месяц.",
                            "quantity": "1.00",
                            "amount": {"value": 149, "currency": "RUB"},
                            "vat_code": 4,
                            "payment_mode": "full_payment",
                        },
                    ],
                }
            }
        ),
        price=14900,
        stars_price=149,
        is_active=False,
    )


def remove_vpn_product_and_product_codes(apps, schema_editor) -> None:
    product_model = apps.get_model("payments", "Product")
    product_model.objects.filter(code=VPN_30D).delete()
    product_model.objects.filter(code=MTPROTO_30D).update(code=None)


class Migration(migrations.Migration):
    dependencies = [("payments", "0005_gift_certificates")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="code",
            field=models.CharField(max_length=32, null=True, unique=True, verbose_name="код"),
        ),
        migrations.RunPython(
            add_product_codes_and_vpn_product,
            remove_vpn_product_and_product_codes,
        ),
        migrations.AlterField(
            model_name="product",
            name="code",
            field=models.CharField(max_length=32, unique=True, verbose_name="код"),
        ),
        migrations.AlterField(
            model_name="payment",
            name="kind",
            field=models.CharField(
                choices=[
                    ("subscription", "Подписка"),
                    ("vpn_subscription", "VPN-подписка"),
                    ("gift_certificate", "Подарочный сертификат"),
                ],
                default="subscription",
                max_length=32,
                verbose_name="тип платежа",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=models.Q(kind="vpn_subscription"),
                fields=("provider", "charge_id", "kind"),
                name="uniq_vpn_subscription_payment_identity",
            ),
        ),
    ]
