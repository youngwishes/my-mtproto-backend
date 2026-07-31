from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.vpn.models import VPNInstance, VPNSubscription
from apps.vpn.services import (
    get_expire_vpn_subscriptions_service,
    get_schedule_profiles_service,
)


@admin.register(VPNSubscription)
class VPNSubscriptionAdmin(admin.ModelAdmin):
    list_select_related = ["user"]
    list_display = ["pk", "user", "expired_at", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["user__username", "user__telegram_username"]
    actions = ["deactivate_subscriptions"]

    @admin.action(description="Деактивировать подписку")
    def deactivate_subscriptions(
        self,
        request: HttpRequest,
        queryset: QuerySet[VPNSubscription],
    ) -> None:
        deactivated_count = get_expire_vpn_subscriptions_service().deactivate(
            subscriptions=queryset,
        )
        if deactivated_count:
            self.message_user(request, "VPN-подписка деактивирована.")
        else:
            self.message_user(request, "Выбранные VPN-подписки уже неактивны.")


@admin.register(VPNInstance)
class VPNInstanceAdmin(admin.ModelAdmin):
    list_display = ["pk", "number", "name", "location", "is_active"]
    list_editable = ["number", "is_active"]
    ordering = ["number", "pk"]
    actions = ["backfill_profiles"]

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.is_active = False
        super().save_model(request, obj, form, change)

    @admin.action(description="Подготовить выбранную неактивную ноду")
    def backfill_profiles(self, request, queryset) -> None:
        instances = list(queryset)
        if len(instances) != 1:
            self.message_user(
                request,
                "Выберите ровно одну неактивную VPN-ноду.",
                level="error",
            )
            return

        instance = instances[0]
        if instance.is_active:
            self.message_user(
                request,
                "Backfill доступен только для неактивной VPN-ноды.",
                level="error",
            )
            return

        get_schedule_profiles_service().backfill(instance_id=instance.pk)
        self.message_user(request, "Backfill VPN-профилей поставлен в очередь.")
