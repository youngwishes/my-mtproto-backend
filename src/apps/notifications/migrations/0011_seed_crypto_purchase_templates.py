from __future__ import annotations

from django.db import migrations


TEMPLATES = (
    {
        "slug": "crypto_vpn_purchased",
        "title": "Crypto Pay: результат VPN",
        "text": (
            "✅ <b>VPN-подписка активирована</b>\n\n"
            "Действует до: <b>{expired_at}</b>\n\n"
            "Subscription-ссылка:\n<code>{subscription_url}</code>"
        ),
    },
    {
        "slug": "crypto_gift_certificate_purchased",
        "title": "Crypto Pay: подарочный сертификат",
        "text": (
            "🎁 <b>Подарочный сертификат готов</b>\n\n"
            "Код: <code>{code}</code>"
        ),
    },
)


def forwards(apps, schema_editor) -> None:
    template_model = apps.get_model("notifications", "NotificationTemplate")
    for template in TEMPLATES:
        template_model.objects.get_or_create(
            slug=template["slug"],
            defaults=template,
        )


def backwards(apps, schema_editor) -> None:
    template_model = apps.get_model("notifications", "NotificationTemplate")
    template_model.objects.filter(
        slug__in=[template["slug"] for template in TEMPLATES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("notifications", "0010_seed_vpn_templates")]

    operations = [migrations.RunPython(forwards, backwards)]
