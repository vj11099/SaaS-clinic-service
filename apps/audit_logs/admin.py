from django.contrib import admin
from .models import RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    actions = None
    list_display = [
        'method', 'path', 'user', 'status_code', 'is_failed',
        'timestamp', 'ip_address', 'response_time_ms'
    ]
    # list_filter = ['is_active', 'is_staff', 'created_at']
    # search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-timestamp']

    readonly_fields = [
        'method', 'path', 'user', 'status_code', 'is_failed',
        'timestamp', 'response_time_ms'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
