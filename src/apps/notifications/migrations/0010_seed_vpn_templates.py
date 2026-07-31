from __future__ import annotations

from django.db import migrations


TEMPLATES = [
    {
        "slug": "vpn_before_expiry_1day",
        "title": "VPN: напоминание за 1 день",
        "text": "⚠️ <b>VPN-подписка истекает завтра.</b>\n\nПродли VPN, чтобы доступ не прерывался.",
        "button_text": "⚡ Продлить VPN",
        "button_url": "",
        "button_callback_data": "vpn",
    },
    {
        "slug": "vpn_before_expiry_1hour",
        "title": "VPN: напоминание за 1 час",
        "text": "⚠️ <b>VPN-подписка истекает сегодня.</b>\n\nПродли VPN, чтобы доступ не прерывался.",
        "button_text": "⚡ Продлить VPN",
        "button_url": "",
        "button_callback_data": "vpn",
    },
    {
        "slug": "vpn_deactivated",
        "title": "VPN: подписка отключена",
        "text": "🔒 <b>VPN-подписка отключена.</b>\n\nПродли VPN, чтобы снова получить доступ.",
        "button_text": "⚡ Продлить VPN",
        "button_url": "",
        "button_callback_data": "vpn",
    },
]


def forwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for template in TEMPLATES:
        NotificationTemplate.objects.create(**template)


def backwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(slug__in=[template["slug"] for template in TEMPLATES]).delete()


class Migration(migrations.Migration):
    dependencies = [("notifications", "0009_update_proxy_link_with_message_template")]

    operations = [migrations.RunPython(forwards, backwards)]
