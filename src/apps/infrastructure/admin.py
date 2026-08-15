from __future__ import annotations

from django.contrib import admin

from apps.infrastructure.models import ProjectServer


@admin.register(ProjectServer)
class ProjectServerAdmin(admin.ModelAdmin):
    list_display = (
        "ipv4",
        "hosting",
        "price",
        "currency",
        "next_payment_date",
        "description",
        "is_active",
    )
    ordering = ("next_payment_date", "ipv4")
    list_select_related = ("hosting",)
    search_fields = ("ipv4", "hosting__name", "description")
    list_filter = ("is_active", "hosting", "currency")
    list_editable = ("price", "currency", "next_payment_date", "is_active")
