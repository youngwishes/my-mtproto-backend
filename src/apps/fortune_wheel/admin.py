from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.fortune_wheel.models import FortuneSpin


@admin.register(FortuneSpin)
class FortuneSpinAdmin(admin.ModelAdmin):
    actions = None
    list_display = ("id", "user", "prize_apples", "created_at")
    list_filter = ("prize_apples", "created_at")
    search_fields = ("user__username", "user__telegram_username")
    list_select_related = ("user",)
    ordering = ("-created_at", "-pk")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> bool:
        return False

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> tuple[str, ...]:
        return tuple(field.name for field in self.model._meta.fields)
