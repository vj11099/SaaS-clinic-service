"""
Subscription Admin
subscriptions/admin.py
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import SubscriptionPlan, SubscriptionHistory


# @admin.register(SubscriptionPlan)
# class SubscriptionPlanAdmin(admin.ModelAdmin):
#     list_display = [
#         'name',
#         'price',
#         'billing_interval',
#         'max_members',
#         'is_active',
#         'is_public',
#         'sort_order',
#         'subscriber_count',
#     ]
#     list_filter = ['billing_interval', 'is_active', 'is_public']
#     search_fields = ['name', 'slug', 'description']
#     prepopulated_fields = {'slug': ('name',)}
#     ordering = ['sort_order', 'price']
#
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'slug', 'description')
#         }),
#         ('Pricing', {
#             'fields': ('price', 'billing_interval')
#         }),
#         ('Limits & Features', {
#             'fields': ('max_members', 'features')
#         }),
#         ('Visibility', {
#             'fields': ('is_active', 'is_public', 'sort_order')
#         }),
#     )
#
#     def subscriber_count(self, obj):
#         """Show number of organizations subscribed to this plan"""
#         count = obj.organizations.filter(
#             subscription_status__in=['active']).count()
#         return format_html('<strong>{}</strong>', count)
#
#     subscriber_count.short_description = 'Active Subscribers'


# @admin.register(SubscriptionHistory)
# class SubscriptionHistoryAdmin(admin.ModelAdmin):
#     list_display = [
#         'organization_link',
#         'plan_link',
#         'action',
#         'performed_by_email',
#         'start_date',
#         'end_date',
#         'created_at',
#     ]
#     list_filter = ['action', 'created_at']
#     search_fields = [
#         'organization__name',
#         'plan__name',
#         'performed_by_email',
#         'notes'
#     ]
#     readonly_fields = [
#         'organization',
#         'plan',
#         'previous_plan',
#         'action',
#         'performed_by_email',
#         'start_date',
#         'end_date',
#         'metadata',
#         'notes',
#         'created_at',
#     ]
#     ordering = ['-created_at']
#     date_hierarchy = 'created_at'
#
#     fieldsets = (
#         ('Subscription Details', {
#             'fields': ('organization', 'plan', 'previous_plan', 'action')
#         }),
#         ('Action Information', {
#             'fields': ('performed_by_email', 'start_date', 'end_date')
#         }),
#         ('Additional Information', {
#             'fields': ('metadata', 'notes', 'created_at')
#         }),
#     )
#
#     def organization_link(self, obj):
#         """Create a link to the organization"""
#         url = reverse('admin:organizations_organization_change',
#                       args=[obj.organization.id])
#         return format_html('<a href="{}">{}</a>', url, obj.organization.name)
#
#     organization_link.short_description = 'Organization'
#
#     def plan_link(self, obj):
#         """Create a link to the plan"""
#         if obj.plan:
#             url = reverse(
#                 'admin:subscriptions_subscriptionplan_change', args=[obj.plan.id])
#             return format_html('<a href="{}">{}</a>', url, obj.plan.name)
#         return '-'
#
#     plan_link.short_description = 'Plan'
#
#     def has_add_permission(self, request):
#         """Disable manual addition of history records"""
#         return False
#
#     def has_delete_permission(self, request, obj=None):
#         """Disable deletion of history records"""
#         return False
#
#
# # Optional: Inline admin for Organization model
# class SubscriptionHistoryInline(admin.TabularInline):
#     model = SubscriptionHistory
#     extra = 0
#     max_num = 0
#     can_delete = False
#     readonly_fields = [
#         'plan',
#         'action',
#         'performed_by_email',
#         'start_date',
#         'end_date',
#         'created_at',
#     ]
#     fields = ['action', 'plan', 'performed_by_email', 'created_at']
#     ordering = ['-created_at']
#
#     def has_add_permission(self, request, obj=None):
#         return False


"""
Add to your organizations/admin.py:

from subscriptions.admin import SubscriptionHistoryInline

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    ...
    inlines = [SubscriptionHistoryInline]
"""
