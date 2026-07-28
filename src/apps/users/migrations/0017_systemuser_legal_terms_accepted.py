from __future__ import annotations

from django.db import migrations, models


def accept_existing_users(apps, schema_editor) -> None:
    SystemUser = apps.get_model("users", "SystemUser")
    SystemUser.objects.all().update(legal_terms_accepted=True)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_normalize_none_usernames"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemuser",
            name="legal_terms_accepted",
            field=models.BooleanField(
                default=False,
                db_default=False,
                verbose_name="юридические условия приняты",
            ),
        ),
        migrations.RunPython(
            accept_existing_users,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
