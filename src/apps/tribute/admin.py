from django.contrib import admin

from apps.tribute.models import TributeDigitalPayment


@admin.register(TributeDigitalPayment)
class TributeDigitalPaymentAdmin(admin.ModelAdmin):
    list_display = ["name"]
