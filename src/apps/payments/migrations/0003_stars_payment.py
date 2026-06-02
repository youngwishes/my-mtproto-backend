import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_payment_provider_payment_charge_id_alter_payment_key'),
    ]

    operations = [
        migrations.RenameField(
            model_name='payment',
            old_name='provider_payment_charge_id',
            new_name='charge_id',
        ),
        migrations.AlterField(
            model_name='payment',
            name='charge_id',
            field=models.CharField(blank=True, verbose_name='ID платежа у провайдера'),
        ),
        migrations.AddField(
            model_name='payment',
            name='provider',
            field=models.CharField(
                choices=[('yukassa', 'ЮKassa'), ('stars', 'Telegram Stars')],
                default='yukassa',
                max_length=16,
                verbose_name='провайдер',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='stars_price',
            field=models.PositiveIntegerField(default=60, verbose_name='цена в звёздах'),
        ),
    ]
