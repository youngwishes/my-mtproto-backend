from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.selectors import get_all_active_vds_instances
from apps.vds.tasks import migrate_vds_keys_task, remove_dead_keys_from_vds_task, sync_keys_to_vds_task


def _key_is_valid(key: MTPRotoKey) -> bool:
    """Ключ живой: активен, не удалён и не истёк — для такого ссылка работает."""
    return bool(
        key.is_active
        and not key.was_deleted
        and key.expired_date
        and key.expired_date > timezone.now()
    )


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
        "is_keys_available",
    ]
    list_editable = ["is_active", "is_healthy", "is_keys_available", "number"]
    actions = (migrate_vds_keys, remove_dead_keys, sync_keys_to_vds)


@admin.register(MTPRotoKey)
class MTPRotoKeyAdmin(admin.ModelAdmin):
    list_select_related = ["user"]
    list_display = ["pk", "__str__", "telegram_username_link", "active_proxy_link", "expired_date"]
    list_filter = ["was_deleted", "is_active", "user_notified"]

    search_fields = ("user__telegram_username", "user__username")

    _example_server_name: str | None = None

    def get_queryset(self, request):
        # «Любой сервер» как пример хоста ссылки — берём один раз на весь список
        qs = super().get_queryset(request)
        self._example_server_name = (
            get_all_active_vds_instances().values_list("name", flat=True).first()
        )
        return qs

    @admin.display(description="Активная ссылка")
    def active_proxy_link(self, obj):
        if not self._example_server_name or not _key_is_valid(obj):
            return "—"
        link = obj.get_proxy_link(server_name=self._example_server_name)
        return format_html('<a href="{}">{}</a>', link, link)

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
