from __future__ import annotations

from django.contrib import admin

from apps.notifications.models import Mailing, NotificationTemplate
from apps.notifications.tasks import send_mailing_task


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("slug", "title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ("template", "filter_type", "status", "created_at", "sent_at")
    list_filter = ("status", "filter_type")
    readonly_fields = ("status", "sent_at", "created_at", "updated_at")
    actions = ["send_mailing"]

    @admin.action(description="Отправить рассылку")
    def send_mailing(self, request, queryset) -> None:
        from apps.notifications.enums import MailingStatus

        for mailing in queryset.filter(status=MailingStatus.DRAFT):
            send_mailing_task.delay(mailing.id)
        self.message_user(request, f"Запущено рассылок: {queryset.count()}")
