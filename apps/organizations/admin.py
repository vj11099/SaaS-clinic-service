# from django.contrib import admin
# from django.db import connection
# from .models import Organization, Domain


# @admin.register(Organization)
# class OrganizationAdmin(admin.ModelAdmin):
#     list_display = ['name', 'schema_name',
#                     'is_active', 'created_at']
#     list_filter = ['is_active', 'created_at']
#     search_fields = ['name', 'schema_name', 'contact_email']
#     readonly_fields = ['created_at', 'updated_at', 'schema_name']
#
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'schema_name', 'description')
#         }),
#         ('Contact Information', {
#             'fields': ('contact_email', 'contact_phone')
#         }),
#         ('Settings', {
#             'fields': ('max_users', 'is_active')
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
#
#
# @admin.register(Domain)
# class DomainAdmin(admin.ModelAdmin):
#     list_display = ['domain', 'tenant', 'is_primary']
#     list_filter = ['is_primary']
#     search_fields = ['domain', 'tenant__name']
