from django.contrib import admin
from django.utils.html import format_html

from apps.vds.models import VDSInstance, MTPRotoKey


@admin.register(VDSInstance)
class VDSInstanceAdmin(admin.ModelAdmin):
    list_display = ["pk", "name", "ip_address", "port", "number", "is_active"]


@admin.register(MTPRotoKey)
class MTPRotoKeyAdmin(admin.ModelAdmin):
    list_select_related = ["user", "vds"]
    list_display = ["pk", "__str__", "telegram_username_link", "vds", "expired_date"]
    list_filter = ["vds", "was_deleted", "is_active"]

    search_fields = ("user__telegram_username", "user__username")

    @admin.display(description="Пользователь", ordering="telegram_username")
    def telegram_username_link(self, obj):
        if obj.user.telegram_username:
            username = obj.user.telegram_username.lstrip('@')
            return format_html(
                '<a href="https://t.me/{}" target="_blank">{}</a>',
                username,
                obj.user.telegram_username
            )
        return obj.user.username
