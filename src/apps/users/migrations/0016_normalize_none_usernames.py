from __future__ import annotations

from django.db import migrations


def normalize_none_usernames(apps, schema_editor):
    """Чистим литерал "None", который писал старый бот (str(None)).

    telegram_username "None" -> "" (поле NOT NULL).
    invited_from_username "None" -> NULL (поле nullable).
    """
    SystemUser = apps.get_model("users", "SystemUser")
    SystemUser.objects.filter(telegram_username="None").update(telegram_username="")
    SystemUser.objects.filter(invited_from_username="None").update(
        invited_from_username=None
    )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_remove_systemuser_new_link_sent"),
    ]

    operations = [
        migrations.RunPython(
            normalize_none_usernames,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
