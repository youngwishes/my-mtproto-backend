from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0014_backfill_apple_cashback_purchases")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="provider_data",
            field=models.TextField(default="{}", verbose_name="provider_data"),
        ),
        migrations.AlterField(
            model_name="product",
            name="send_email_to_provider",
            field=models.BooleanField(
                default=False,
                verbose_name="отправить email продавцу",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="need_email",
            field=models.BooleanField(
                default=False,
                verbose_name="спрашивать почту",
            ),
        ),
        migrations.RemoveField(
            model_name="product",
            name="provider_data",
        ),
        migrations.RemoveField(
            model_name="product",
            name="send_email_to_provider",
        ),
        migrations.RemoveField(
            model_name="product",
            name="need_email",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="payment",
                    name="provider",
                    field=models.CharField(
                        choices=[
                            ("stars", "Telegram Stars"),
                            ("crypto_pay", "Crypto Pay"),
                            ("platega", "Platega"),
                        ],
                        default="stars",
                        max_length=16,
                        verbose_name="провайдер",
                    ),
                ),
            ],
        ),
    ]
