from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vds", "0021_hosting_vdsinstance_expired_at_vdsinstance_hosting"),
    ]

    operations = [
        migrations.AddField(
            model_name="vdsinstance",
            name="tls_domain",
            field=models.CharField(default="mtprotokeys.com", verbose_name="TLS-домен"),
            preserve_default=False,
        ),
    ]
