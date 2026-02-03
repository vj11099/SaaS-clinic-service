from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username',
                    'is_active', 'created_at']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Personal info', {'fields': ('first_name',
         'last_name', 'email', 'phone')}),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            ),
        }),
        ('Important dates', {'fields': ('last_login',
         'date_joined', 'created_at', 'updated_at')}),
    )

    readonly_fields = ['created_at', 'updated_at', 'date_joined']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email'),
        }),
    )
