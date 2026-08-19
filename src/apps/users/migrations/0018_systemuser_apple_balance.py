from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_systemuser_legal_terms_accepted"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemuser",
            name="apple_balance",
            field=models.PositiveIntegerField(default=0, verbose_name="баланс яблок"),
        ),
        migrations.AddConstraint(
            model_name="systemuser",
            constraint=models.CheckConstraint(
                condition=models.Q(("apple_balance__gte", 0)),
                name="system_user_apple_balance_non_negative",
            ),
        ),
    ]
