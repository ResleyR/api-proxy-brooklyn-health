from django.contrib import admin

from .models import APIKey, RequestLog, Service


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key")
    readonly_fields = ("key", "created_at")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "base_url", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "method",
        "path",
        "api_key",
        "service",
        "status_code",
        "duration_ms",
    )
    list_filter = ("method", "status_code", "service")
    search_fields = ("path",)
    date_hierarchy = "timestamp"
    readonly_fields = (
        "api_key",
        "service",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
