from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html

from apps.users.models import SystemUser
from apps.users.tasks import (
    send_free_link_to_user_task,
    send_invite_to_chat_task,
    update_user_link_task,
)


@admin.action(description="Сделать рассылку «подпишись на канал».")
def send_invite_to_channel(modeladmin, request, queryset):
    send_invite_to_chat_task.delay(
        telegram_ids=list(queryset.values_list("username", flat=True))
    )


@admin.action(description="Отправить бесплатную ссылку.")
def send_free_link_to_user(modeladmin, request, queryset):
    send_free_link_to_user_task.delay(
        telegram_ids=list(queryset.values_list("username", flat=True))
    )


@admin.action(description="Сделать рассылку про перевыпуск ссылки.")
def notify_about_update_link(modeladmin, request, queryset):
    update_user_link_task.delay(
        telegram_ids=list(
            queryset.filter(first_month_free_used=True, notified_update_link=False).values_list("username", flat=True)
        )
    )
    queryset.filter(first_month_free_used=True).update(notified_update_link=True)


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "username",
        "telegram_username_link",
        "invited_from_username",
        "first_month_free_used",
        "is_active",
        "date_joined",
    ]
    search_fields = ("username", "telegram_username")
    list_filter = [
        "is_active",
        "first_month_free_used",
    ]
    actions = [send_free_link_to_user, send_invite_to_channel, notify_about_update_link]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("keys")
            .annotate(mtproto_key=F("keys"))
        )

    @admin.display(description="Telegram Username", ordering="telegram_username")
    def telegram_username_link(self, obj):
        if obj.telegram_username:
            username = obj.telegram_username.lstrip("@")
            return format_html(
                '<a href="https://t.me/{}" target="_blank">{}</a>',
                username,
                obj.telegram_username,
            )
        return "-"
