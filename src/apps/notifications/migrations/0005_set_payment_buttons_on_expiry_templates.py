from __future__ import annotations

from django.db import migrations


SLUGS_WITH_PAYMENT_BUTTONS = [
    "before_expiry_1day",
    "before_expiry_1hour",
    "link_deactivated",
]

def forwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(
        slug__in=SLUGS_WITH_PAYMENT_BUTTONS,
    ).update(
        include_payment_buttons=True,
        button_text="",
    )


def backwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(
        slug__in=SLUGS_WITH_PAYMENT_BUTTONS,
    ).update(
        include_payment_buttons=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_mailing_failed_count_mailing_sent_count_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
