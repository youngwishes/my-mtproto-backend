from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor) -> None:
    template_model = apps.get_model("notifications", "NotificationTemplate")
    template = template_model.objects.get(slug="sorry_server_error")
    template.text = template.text.replace(
        "@mtproto_keys",
        "@mtprotokeys_support",
        1,
    )
    template.save(update_fields=["text"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0011_seed_crypto_purchase_templates")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
