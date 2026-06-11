from __future__ import annotations

from django.db import migrations


def update_proxy_purchased_template(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    try:
        template = NotificationTemplate.objects.get(slug="proxy_purchased")
        template.text = (
            "🎉 <b>Спасибо за покупку!</b>\n\n"
            "⏳ Подписка активна до: <b>{expired_date}</b>\n\n"
            "👇 Нажми «Мои серверы» чтобы подключиться ко всем серверам"
        )
        template.button_text = "📡 Мои серверы"
        template.button_url = ""
        template.button_callback_data = "my_servers"
        template.save()
    except NotificationTemplate.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0006_notificationtemplate_button_callback_data"),
    ]

    operations = [
        migrations.RunPython(
            update_proxy_purchased_template,
            migrations.RunPython.noop,
        ),
    ]
