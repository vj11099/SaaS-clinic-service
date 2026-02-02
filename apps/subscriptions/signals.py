# from django.apps import AppConfig
# from django.db.models.signals import post_save, post_delete, pre_save
# from django.dispatch import receiver
# from django.core.exceptions import ValidationError
#
#
# # Example signal handlers - adjust based on the Membership model
#
# @receiver(pre_save, sender='memberships.Membership')
# def check_member_limit_before_add(sender, instance, **kwargs):
#     """
#     Check if organization can add member before saving
#     Only check for new members (not updates)
#     """
#     if instance._state.adding:  # New member
#         organization = instance.organization
#
#         # Check if subscription is active
#         if not organization.is_subscription_active():
#             raise ValidationError(
#                 "Cannot add member: Organization subscription has expired"
#             )
#
#         # Check member limit
#         if not organization.can_add_member():
#             raise ValidationError(
#                 f"Cannot add member: Member limit reached. "
#                 f"Current: {organization.current_member_count}, "
#                 f"Limit: {organization.get_member_limit()}"
#             )
#
#
# @receiver(post_save, sender='memberships.Membership')
# def update_member_count_on_add(sender, instance, created, **kwargs):
#     """Update organization member count when member is added"""
#     if created:
#         organization = instance.organization
#         organization.current_member_count += 1
#         organization.save(update_fields=['current_member_count'])
#
#
# @receiver(post_delete, sender='memberships.Membership')
# def update_member_count_on_delete(sender, instance, **kwargs):
#     """Update organization member count when member is removed"""
#     organization = instance.organization
#     organization.current_member_count = max(
#         0, organization.current_member_count - 1)
#     organization.save(update_fields=['current_member_count'])
#
#
# # Subscription status change signals
#
# @receiver(post_save, sender='subscriptions.SubscriptionHistory')
# def handle_subscription_change(sender, instance, created, **kwargs):
#     """
#     Handle actions when subscription status changes
#     """
#     if not created:
#         return
#
#     organization = instance.organization
#     action = instance.action
#
#     # Handle different actions
#     if action == 'expired':
#         # Subscription expired - send notifications, log users out, etc.
#         from subscriptions.tasks import cleanup_expired_sessions
#         cleanup_expired_sessions.delay(organization.id)
#
#     elif action == 'suspended':
#         # Organization suspended - more aggressive actions
#         pass
#
#     elif action == 'cancelled':
#         # Subscription cancelled - send feedback request
#         pass
#
#     elif action in ['subscribed', 'renewed', 'upgraded']:
#         # New subscription or renewal - send welcome/thank you email
#         pass
#
#
# # Example: Log out users when subscription expires
#
# def logout_all_organization_users(organization):
#     """
#     Log out all users of an organization
#     This is called when subscription expires or is suspended
#     """
#     from django.contrib.sessions.models import Session
#     from django.utils import timezone
#
#     # Get all active sessions
#     sessions = Session.objects.filter(expire_date__gte=timezone.now())
#
#     for session in sessions:
#         session_data = session.get_decoded()
#         user_id = session_data.get('_auth_user_id')
#
#         if user_id:
#             # Check if user belongs to this organization
#             # This depends on the user-organization relationship
#             # Example:
#             # from memberships.models import Membership
#             # if Membership.objects.filter(
#             #     user_id=user_id,
#             #     organization=organization
#             # ).exists():
#             #     session.delete()
#             pass
#
#
# # Signal to connect apps
#
#
# class SubscriptionsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'subscriptions'
#
#     def ready(self):
#         import subscriptions.signals  # noqa
#
#
# """
# Add this to subscriptions/apps.py:
#
# from django.apps import AppConfig
#
# class SubscriptionsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'subscriptions'
#
#     def ready(self):
#         import subscriptions.signals
#
# And make sure to use it in __init__.py:
#
# default_app_config = 'subscriptions.apps.SubscriptionsConfig'
# """
