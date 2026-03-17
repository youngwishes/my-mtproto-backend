from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import Payment, Product


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "provider_payment_charge_id",
        "telegram_username_link",
        "key",
        "created_at",
    ]
    list_select_related = ["user", "key"]

    @admin.display(description="Пользователь", ordering="telegram_username")
    def telegram_username_link(self, obj):
        if obj.user.telegram_username:
            username = obj.user.telegram_username.lstrip("@")
            return format_html(
                '<a href="https://t.me/{}" target="_blank">{}</a>',
                username,
                obj.user.telegram_username,
            )
        return obj.user.username


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "is_active",
        "title",
        "price",
        "currency",
        "send_email_to_provider",
        "need_email",
    ]
