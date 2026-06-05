from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_remove_systemuser_is_agree"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemuser",
            name="notified_update_link",
        ),
    ]
