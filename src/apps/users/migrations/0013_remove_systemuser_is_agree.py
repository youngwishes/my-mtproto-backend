from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_systemuser_is_agree"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemuser",
            name="is_agree",
        ),
    ]
