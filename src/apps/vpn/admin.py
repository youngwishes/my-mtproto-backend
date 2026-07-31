from django.contrib import admin

from apps.vpn.models import VPNInstance, VPNSubscription
from apps.vpn.services import get_schedule_profiles_service


@admin.register(VPNSubscription)
class VPNSubscriptionAdmin(admin.ModelAdmin):
    list_select_related = ["user"]
    list_display = ["pk", "user", "expired_at", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["user__username", "user__telegram_username"]


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
