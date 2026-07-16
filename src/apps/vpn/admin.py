from __future__ import annotations

from django import forms
from django.contrib import admin

from apps.vpn.models import (
    VPNAccess,
    VPNAccessNodeApply,
    VPNAccessNodeRevisionEvidence,
    VPNNode,
    VPNPurchase,
)
from apps.vpn.services import get_deactivate_vpn_refund_service


class VPNNodeAdminForm(forms.ModelForm):
    class Meta:
        model = VPNNode
        fields = "__all__"

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        forbidden = {
            key
            for key in self.data
            if key in {"private_key", "target", "reality_private_key", "reality_target"}
            and self.data.get(key)
        }
        if forbidden:
            raise forms.ValidationError(
                "Приватный REALITY key и REALITY target хранятся только на ноде."
            )
        return cleaned_data


@admin.register(VPNAccess)
class VPNAccessAdmin(admin.ModelAdmin):
    list_display = ("pk", "user", "state", "expired_at", "masked_subscription_token")
    list_filter = ("state", "is_active")
    list_select_related = ("user", "disabled_by")
    readonly_fields = ("masked_subscription_token", "created_at", "updated_at")
    exclude = ("subscription_token",)
    search_fields = ("user__username", "user__telegram_username")
    actions = ("deactivate_after_refund",)

    @admin.action(description="Деактивировать после возврата")
    def deactivate_after_refund(self, request, queryset) -> None:
        service = get_deactivate_vpn_refund_service()
        changed = sum(
            service(access=access, actor=request.user, reason="admin refund")
            for access in queryset
        )
        self.message_user(request, f"Деактивировано VPN-доступов: {changed}")

    @admin.display(description="Subscription token")
    def masked_subscription_token(self, obj: VPNAccess) -> str:
        token = obj.subscription_token
        return f"{token[:6]}…{token[-4:]}" if token else "—"


@admin.register(VPNPurchase)
class VPNPurchaseAdmin(admin.ModelAdmin):
    list_display = ("pk", "payment", "access", "period_days", "expired_at_after")
    list_select_related = ("payment", "access")
    readonly_fields = ("payment", "access", "period_days", "expired_at_after")


@admin.register(VPNNode)
class VPNNodeAdmin(admin.ModelAdmin):
    form = VPNNodeAdminForm
    list_display = (
        "pk",
        "name",
        "number",
        "location",
        "health_state",
        "data_plane_state",
        "is_access_available",
        "is_active",
    )
    list_editable = ("number", "is_access_available", "is_active")
    list_filter = (
        "health_state",
        "data_plane_state",
        "is_access_available",
        "is_active",
    )


@admin.register(VPNAccessNodeApply)
class VPNAccessNodeApplyAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "access",
        "node",
        "desired_revision",
        "applied_revision",
        "status",
        "last_attempt_at",
    )
    list_filter = ("status", "is_active")
    list_select_related = ("access", "node")
    readonly_fields = (
        "access",
        "node",
        "desired_revision",
        "applied_revision",
        "status",
        "last_attempt_at",
        "last_error_code",
    )


@admin.register(VPNAccessNodeRevisionEvidence)
class VPNAccessNodeRevisionEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "access",
        "node",
        "revision",
        "applied_revision",
        "status",
        "is_serving",
    )
    list_filter = ("status", "is_serving", "is_active")
    readonly_fields = (
        "access",
        "node",
        "revision",
        "applied_revision",
        "status",
        "is_serving",
        "last_attempt_at",
        "last_error_code",
    )
