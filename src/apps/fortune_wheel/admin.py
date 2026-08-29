from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AdminSplitDateTime
from django.http import HttpRequest

from apps.fortune_wheel.models import FortuneSpin


class FortuneSpinAdminForm(forms.ModelForm):
    field_order = ("is_active", "created_at", "user", "prize_apples")
    created_at = forms.SplitDateTimeField(
        label=FortuneSpin._meta.get_field("created_at").verbose_name,
        widget=AdminSplitDateTime,
    )

    class Meta:
        model = FortuneSpin
        fields = ("is_active", "user", "prize_apples")

    def save(self, commit: bool = True) -> FortuneSpin:
        spin = super().save(commit=False)
        spin.created_at = self.cleaned_data["created_at"]
        if commit:
            spin.save()
            self.save_m2m()
        return spin


@admin.register(FortuneSpin)
class FortuneSpinAdmin(admin.ModelAdmin):
    actions = None
    form = FortuneSpinAdminForm
    list_display = ("id", "user", "prize_apples", "created_at")
    list_filter = ("prize_apples", "created_at")
    search_fields = ("user__username", "user__telegram_username")
    list_select_related = ("user",)
    ordering = ("-created_at", "-pk")
    readonly_fields = ("id", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def get_form(
        self,
        request: HttpRequest,
        obj: object | None = None,
        change: bool = False,
        **kwargs: object,
    ) -> type[forms.ModelForm]:
        kwargs["fields"] = FortuneSpinAdminForm._meta.fields
        return super().get_form(request, obj, change=change, **kwargs)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> bool:
        return False
