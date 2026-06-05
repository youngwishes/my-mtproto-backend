from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_remove_systemuser_notified_update_link"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemuser",
            name="new_link_sent",
        ),
    ]
