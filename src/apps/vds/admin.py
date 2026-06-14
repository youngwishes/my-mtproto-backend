from django.contrib import admin
from django.utils.html import format_html

from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.tasks import migrate_vds_keys_task, remove_dead_keys_from_vds_task, sync_keys_to_vds_task


@admin.action(description="Перенести все ключи на другие VDS-машины.")
def migrate_vds_keys(modeladmin, request, queryset):
    for instance in queryset:
        migrate_vds_keys_task.delay(from_instance_id=instance.pk)


@admin.action(description="Удалить протухшие ключи с выбранных VDS-серверов.")
def remove_dead_keys(modeladmin, request, queryset):
    for instance in queryset:
        remove_dead_keys_from_vds_task.delay(instance_id=instance.pk)


@admin.action(description="Синхронизировать все активные ключи БД на выбранные VDS-серверы.")
def sync_keys_to_vds(modeladmin, request, queryset):
    for instance in queryset:
        sync_keys_to_vds_task.delay(instance_id=instance.pk)


@admin.register(VDSInstance)
class VDSInstanceAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "internal_ip_address",
        "number",
        "is_active",
        "is_healthy",
    ]
    list_editable = ["is_active", "is_healthy"]
    actions = (migrate_vds_keys, remove_dead_keys, sync_keys_to_vds)


@admin.register(MTPRotoKey)
class MTPRotoKeyAdmin(admin.ModelAdmin):
    list_select_related = ["user"]
    list_display = ["pk", "__str__", "telegram_username_link", "expired_date"]
    list_filter = ["was_deleted", "is_active", "user_notified"]

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
