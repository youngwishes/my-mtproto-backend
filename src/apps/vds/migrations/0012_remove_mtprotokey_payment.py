from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("vds", "0011_mtprotokey_is_winner"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="mtprotokey",
            name="payment",
        ),
    ]
