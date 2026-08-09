from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0011_alter_cryptopaymentintent_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="is_priority",
            field=models.BooleanField(default=False, verbose_name="приоритетный"),
        ),
    ]
