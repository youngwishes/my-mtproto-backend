from django.contrib import admin

from apps.users.models import SystemUser
from apps.users.tasks import (
    send_free_link_to_user_task,
    send_invite_to_chat_task,
)


@admin.action(description="Сделать рассылку «подпишись на канал»")
def send_invite_to_channel(modeladmin, request, queryset):
    send_invite_to_chat_task.delay()


@admin.action(description="Отправить бесплатную ссылку V2")
def send_free_link_to_user(modeladmin, request, queryset):
    send_free_link_to_user_task.delay(
        telegram_ids=queryset.values_list("username", flat=True)
    )


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "username",
        "telegram_username",
        "is_active",
        "date_joined",
        "first_month_free_used",
    ]
    search_fields = ("username", "telegram_username")
    list_filter = [
        "is_active",
        "first_month_free_used",
    ]
    actions = [send_free_link_to_user, send_invite_to_channel]
