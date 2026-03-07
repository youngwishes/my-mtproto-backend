from django.contrib import admin
from apps.payments.models import Product, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "key", "created_at"]
    list_select_related = ["user", "key"]


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
