from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("vds", "0012_remove_mtprotokey_payment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="mtprotokey",
            name="is_winner",
        ),
    ]
