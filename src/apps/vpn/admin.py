from django.contrib import admin

from apps.vpn.models import VPNInstance, VPNSubscription


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
