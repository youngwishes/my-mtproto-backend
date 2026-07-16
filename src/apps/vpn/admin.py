from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core import signing
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from apps.vpn.exceptions import VPNRefundConflict, VPNRefundPurchaseNotCurrent
from apps.vpn.models import (
    VPNAccess,
    VPNAccessNodeApply,
    VPNAccessNodeRevisionEvidence,
    VPNNode,
    VPNPurchase,
)
from apps.vpn.services import get_deactivate_vpn_refund_service

_REFUND_CONFIRMATION_SALT = "vpn.refund-confirmation.v1"
_REFUND_CONFIRMATION_MAX_AGE_SECONDS = 600
_REDACTED_PAYMENT_IDENTITY = "••••••"


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

    @admin.display(description="Subscription token")
    def masked_subscription_token(self, obj: VPNAccess) -> str:
        token = obj.subscription_token
        return f"{token[:6]}…{token[-4:]}" if token else "—"


@admin.register(VPNPurchase)
class VPNPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "safe_payment_identity",
        "access_user",
        "period_days",
        "expired_at_after",
        "refunded_at",
    )
    list_select_related = ("payment", "access", "access__user", "refunded_by")
    readonly_fields = (
        "payment",
        "access",
        "period_days",
        "expired_at_after",
        "refunded_at",
        "refunded_by",
        "refund_reason",
    )
    actions = ("deactivate_after_refund",)

    @admin.display(description="Платёж")
    def safe_payment_identity(self, obj: VPNPurchase) -> str:
        return _REDACTED_PAYMENT_IDENTITY

    @admin.display(description="Пользователь")
    def access_user(self, obj: VPNPurchase) -> str:
        return str(obj.access.user)

    @admin.action(description="Отключить VPN после подтверждённого возврата")
    def deactivate_after_refund(
        self,
        request: HttpRequest,
        queryset: QuerySet[VPNPurchase],
    ) -> HttpResponse | None:
        purchases = list(
            queryset.select_related("payment", "access", "access__user")[:2]
        )
        if len(purchases) != 1:
            self.message_user(
                request,
                "Для безопасного возврата выберите ровно одну VPN-покупку.",
                level=messages.ERROR,
            )
            return None

        purchase = purchases[0]
        if request.POST.get("confirm") != "yes":
            confirmation_token = signing.dumps(
                {
                    "purchase_id": purchase.pk,
                    "state_revision": purchase.access.state_revision,
                    "expired_at": purchase.access.expired_at.isoformat(),
                },
                salt=_REFUND_CONFIRMATION_SALT,
            )
            return TemplateResponse(
                request,
                "admin/vpn/vpnpurchase/refund_confirmation.html",
                {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "title": "Подтвердите отключение VPN после возврата",
                    "purchase": purchase,
                    "safe_payment_identity": self.safe_payment_identity(purchase),
                    "current_expired_at": purchase.access.expired_at,
                    "action_name": "deactivate_after_refund",
                    "confirmation_token": confirmation_token,
                },
            )

        try:
            confirmation = signing.loads(
                request.POST.get("confirmation_token", ""),
                salt=_REFUND_CONFIRMATION_SALT,
                max_age=_REFUND_CONFIRMATION_MAX_AGE_SECONDS,
            )
        except signing.BadSignature:
            confirmation = None
        if confirmation != {
            "purchase_id": purchase.pk,
            "state_revision": purchase.access.state_revision,
            "expired_at": purchase.access.expired_at.isoformat(),
        }:
            self.message_user(
                request,
                "Подтверждение устарело или не соответствует выбранной покупке.",
                level=messages.ERROR,
            )
            return None

        try:
            changed = get_deactivate_vpn_refund_service()(
                purchase=purchase,
                actor=request.user,
                reason="admin confirmed provider refund",
            )
        except (VPNRefundConflict, VPNRefundPurchaseNotCurrent) as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return None
        message = (
            "VPN-доступ отключён; денежный refund у провайдера не выполнялся."
            if changed
            else "Этот платёж уже был обработан как refund; состояние не изменено."
        )
        self.message_user(request, message, level=messages.SUCCESS)
        return None


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
