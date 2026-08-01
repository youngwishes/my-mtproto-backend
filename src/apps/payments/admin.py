from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import GiftCertificate, Payment, Product


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "charge_id",
        "telegram_username_link",
        "key",
        "provider",
        "kind",
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
        "code",
        "title",
        "price",
        "stars_price",
        "currency",
        "send_email_to_provider",
        "need_email",
    ]


@admin.register(GiftCertificate)
class GiftCertificateAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "code",
        "buyer",
        "status",
        "activated_by",
        "expires_at",
        "activated_at",
        "payment",
    ]
    list_filter = ["status", "payment__provider"]
    search_fields = [
        "code",
        "buyer__username",
        "buyer__telegram_username",
        "activated_by__username",
        "activated_by__telegram_username",
        "payment__charge_id",
    ]
    list_select_related = ["buyer", "activated_by", "payment"]
