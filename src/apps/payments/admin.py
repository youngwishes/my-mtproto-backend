from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from apps.payments.models import (
    CryptoPaymentIntent,
    GiftCertificate,
    Payment,
    PaymentMethod,
    PlategaPaymentIntent,
    Product,
)


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


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    actions = None
    list_display = (
        "code",
        "commission_percent",
        "is_active",
        "is_priority",
        "updated_at",
    )
    list_editable = ("commission_percent", "is_active", "is_priority")
    readonly_fields = ("code", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


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


@admin.register(CryptoPaymentIntent)
class CryptoPaymentIntentAdmin(admin.ModelAdmin):
    """Read-only diagnostics for Crypto Pay purchase lifecycle."""

    actions = None
    list_display = [
        "id",
        "public_id",
        "initiator",
        "purchase_kind",
        "rub_amount",
        "status",
        "provider_invoice_id",
        "paid_at",
        "fulfilled_at",
        "notification_sent_at",
        "payment",
    ]
    list_filter = ["status", "purchase_kind"]
    search_fields = ["public_id", "provider_invoice_id"]
    list_select_related = ["initiator", "payment"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def get_readonly_fields(
        self, request: HttpRequest, obj: object | None = None
    ) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(PlategaPaymentIntent)
class PlategaPaymentIntentAdmin(admin.ModelAdmin):
    """Read-only diagnostics for Platega SBP purchase lifecycle."""

    actions = None
    list_display = [
        "id",
        "public_id",
        "initiator",
        "purchase_kind",
        "rub_amount",
        "status",
        "provider_transaction_id",
        "fulfilled_at",
        "notification_sent_at",
        "payment",
    ]
    list_filter = ["status", "purchase_kind"]
    search_fields = ["public_id", "provider_transaction_id"]
    list_select_related = ["initiator", "payment"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def get_readonly_fields(
        self, request: HttpRequest, obj: object | None = None
    ) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)
