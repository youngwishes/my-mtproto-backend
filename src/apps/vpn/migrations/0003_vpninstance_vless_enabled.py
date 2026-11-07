from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vpn", "0002_vpnsubscription_last_reissued_at")]

    operations = [
        migrations.AddField(
            model_name="vpninstance",
            name="vless_enabled",
            field=models.BooleanField(default=True, verbose_name="VLESS включён"),
        ),
    ]
