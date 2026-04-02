from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.tasks import migrate_vds_keys_task


@admin.action(description="Перенести все ключи на другие VDS-машины.")
def migrate_vds_keys(modeladmin, request, queryset):
    for instance in queryset:
        migrate_vds_keys_task.delay(from_instance_id=instance.pk)


@admin.register(VDSInstance)
class VDSInstanceAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "internal_ip_address",
        "number",
        "active_keys_count",
        "not_active_keys_count",
        "user_limit",
        "is_active",
    ]
    list_editable = ["is_active"]
    actions = (migrate_vds_keys,)

    @admin.display(description="Количество активных ключей")
    def active_keys_count(self, obj):
        return obj.keys.filter(is_active=True, was_deleted=False).count()

    @admin.display(description="Количество истекших ключей")
    def not_active_keys_count(self, obj):
        return obj.keys.filter(is_active=False, was_deleted=True).count()

    @admin.display(description="Количество ключей которые истекут завтра")
    def not_active_keys_count(self, obj):
        return obj.keys.filter(
            expired_date__date=(timezone.now() + timedelta(days=1)).date()
        ).count()


@admin.register(MTPRotoKey)
class MTPRotoKeyAdmin(admin.ModelAdmin):
    list_select_related = ["user", "vds"]
    list_display = ["pk", "__str__", "telegram_username_link", "vds", "expired_date", "is_winner"]
    list_filter = ["vds", "was_deleted", "is_active", "is_winner", "user_notified"]

    search_fields = ("user__telegram_username", "user__username")

    @admin.display(description="Пользователь", ordering="telegram_username")
    def telegram_username_link(self, obj):
        if obj.user.telegram_username and obj.user.telegram_username != "None":
            username = obj.user.telegram_username.lstrip("@")
            return format_html(
                '<a href="https://t.me/{}" target="_blank">{}</a>',
                username,
                obj.user.telegram_username,
            )
        return obj.user.username
