from django.contrib import admin
from apps.vds.models import VDSInstance, MTPRotoKey


@admin.register(VDSInstance)
class VDSInstanceAdmin(admin.ModelAdmin):
    list_display = ["pk", "name", "ip_address", "port", "number", "is_active"]


@admin.register(MTPRotoKey)
class MTPRotoKeyAdmin(admin.ModelAdmin):
    list_select_related = ["user", "vds"]
    list_display = ["pk", "token", "user", "vds"]
