from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_systemuser_apple_balance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemuser",
            name="referral_link_activated_count",
            field=models.PositiveSmallIntegerField(
                db_default=0,
                default=0,
                verbose_name="количество активированных реф. ссылок",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="systemuser",
                    name="referral_link_activated_count",
                ),
            ],
        ),
    ]
