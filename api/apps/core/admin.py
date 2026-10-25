"""Staff turn pre-launch mode on and off here, without a deploy (G32, ADR-0038)."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.core.models import SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "prelaunch_mode", "updated_at")
    fields = ("prelaunch_mode", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
