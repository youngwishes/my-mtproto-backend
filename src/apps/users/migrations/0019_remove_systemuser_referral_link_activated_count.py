from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_systemuser_apple_balance"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemuser",
            name="referral_link_activated_count",
        ),
    ]
