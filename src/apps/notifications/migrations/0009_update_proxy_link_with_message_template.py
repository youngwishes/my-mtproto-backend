from __future__ import annotations

from django.db import migrations

_REMOVED_ACTIVE_KEY_LINK = 1
_CONTEXT_RESOLVER_NONE = 0


def migrate_proxy_link_with_message(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    try:
        template = NotificationTemplate.objects.get(slug="proxy_link_with_message")
        template.text = "{text}"
        template.button_text = "📡 Мои серверы"
        template.button_url = ""
        template.button_callback_data = "my_servers"
        template.save()
    except NotificationTemplate.DoesNotExist:
        pass

    # Резолвер ACTIVE_KEY_LINK удалён вместе с reconcile-моделью: сбрасываем
    # осиротевшие рассылки на «без персонального контекста», чтобы они не падали.
    Mailing = apps.get_model("notifications", "Mailing")
    Mailing.objects.filter(context_resolver=_REMOVED_ACTIVE_KEY_LINK).update(
        context_resolver=_CONTEXT_RESOLVER_NONE,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0008_alter_mailing_context_resolver"),
    ]

    operations = [
        migrations.RunPython(
            migrate_proxy_link_with_message,
            migrations.RunPython.noop,
        ),
    ]
