from django.contrib import admin
from apps.users.models import SystemUser

@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    list_display = ["pk", "username", "is_active", "date_joined", "first_month_free_used"]
    search_fields = ("username",)
    list_filter = [
        "is_active",
        "first_month_free_used",
    ]
