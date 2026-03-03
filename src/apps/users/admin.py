from django.contrib import admin

from apps.users.models import SystemUser
from apps.users.tasks import send_free_link_to_user_task


@admin.action(description="Отправить бесплатную ссылку")
def send_free_link_to_user(modeladmin, request, queryset):
    for user in queryset:
        send_free_link_to_user_task.delay(telegram_id=user.username)


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
    actions = [send_free_link_to_user]
