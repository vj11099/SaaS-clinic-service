# """
# Celery Tasks for Subscription Management
# subscriptions/tasks.py
#
# Configure Celery beat schedule in settings.py:
#
# from celery.schedules import crontab
#
# CELERY_BEAT_SCHEDULE = {
#     'check-subscriptions': {
#         'task': 'subscriptions.tasks.check_subscription_statuses',
#         'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
#     },
#     'notify-expiring-subscriptions': {
#         'task': 'subscriptions.tasks.notify_expiring_subscriptions',
#         'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
#     },
# }
# """
# from celery import shared_task
# from django.utils import timezone
# from django.db.models import Q
# from datetime import timedelta
#
# from organizations.models import Organization
# from subscriptions.models import SubscriptionHistory
# from subscriptions.services import SubscriptionService
#
#
# @shared_task
# def check_subscription_statuses():
#     """
#     Check and update all subscription statuses
#     Run this task daily
#     """
#     organizations = Organization.objects.filter(
#         Q(subscription_status='active') | Q(subscription_status='trial')
#     )
#
#     updated_count = 0
#     expired_count = 0
#     suspended_count = 0
#
#     for org in organizations:
#         old_status = org.subscription_status
#         new_status = org.update_subscription_status()
#
#         if old_status != new_status:
#             updated_count += 1
#
#             if new_status == 'expired':
#                 expired_count += 1
#                 SubscriptionHistory.objects.create(
#                     organization=org,
#                     plan=org.subscription_plan,
#                     action='expired',
#                     performed_by_email='system@auto',
#                     end_date=timezone.now(),
#                     notes='Subscription expired automatically'
#                 )
#
#                 # Send expiry notification
#                 send_subscription_expired_email.delay(org.id)
#
#             elif new_status == 'suspended':
#                 suspended_count += 1
#                 SubscriptionHistory.objects.create(
#                     organization=org,
#                     plan=org.subscription_plan,
#                     action='suspended',
#                     performed_by_email='system@auto',
#                     end_date=timezone.now(),
#                     notes='Organization suspended due to expired grace period'
#                 )
#
#                 # Send suspension notification
#                 send_subscription_suspended_email.delay(org.id)
#
#     return {
#         'checked': organizations.count(),
#         'updated': updated_count,
#         'expired': expired_count,
#         'suspended': suspended_count,
#     }
#
#
# @shared_task
# def notify_expiring_subscriptions():
#     """
#     Notify organizations about expiring subscriptions
#     Run this task daily
#     """
#     # Notify for subscriptions expiring in 7 days
#     expiring_7_days = SubscriptionService.get_expiring_subscriptions(
#         days_threshold=7)
#
#     # Notify for subscriptions expiring in 3 days
#     expiring_3_days = SubscriptionService.get_expiring_subscriptions(
#         days_threshold=3)
#
#     # Notify for subscriptions expiring in 1 day
#     expiring_1_day = SubscriptionService.get_expiring_subscriptions(
#         days_threshold=1)
#
#     for org in expiring_7_days:
#         if org.days_until_expiry() == 7:
#             send_subscription_expiring_email.delay(org.id, days=7)
#
#     for org in expiring_3_days:
#         if org.days_until_expiry() == 3:
#             send_subscription_expiring_email.delay(org.id, days=3)
#
#     for org in expiring_1_day:
#         if org.days_until_expiry() == 1:
#             send_subscription_expiring_email.delay(org.id, days=1)
#
#     return {
#         'expiring_7_days': expiring_7_days.count(),
#         'expiring_3_days': expiring_3_days.count(),
#         'expiring_1_day': expiring_1_day.count(),
#     }
#
#
# @shared_task
# def send_subscription_expiring_email(organization_id, days):
#     """Send email notification for expiring subscription"""
#     try:
#         org = Organization.objects.get(id=organization_id)
#
#         # TODO: Implement email sending
#         # Example using Django's send_mail:
#         # from django.core.mail import send_mail
#         #
#         # send_mail(
#         #     subject=f'Your subscription expires in {days} days',
#         #     message=f'Dear {org.name},\n\n'
#         #             f'Your subscription will expire in {days} days on '
#         #             f'{org.subscription_end_date.date()}.\n\n'
#         #             f'Please renew to continue using our services.',
#         #     from_email='noreply@example.com',
#         #     recipient_list=[org.contact_email],
#         # )
#
#         print(f"Sent expiring notification to {
#               org.name} ({org.contact_email}) - {days} days left")
#         return True
#
#     except Organization.DoesNotExist:
#         return False
#
#
# @shared_task
# def send_subscription_expired_email(organization_id):
#     """Send email notification for expired subscription"""
#     try:
#         org = Organization.objects.get(id=organization_id)
#
#         # TODO: Implement email sending
#         print(f"Sent expired notification to {org.name} ({org.contact_email})")
#         return True
#
#     except Organization.DoesNotExist:
#         return False
#
#
# @shared_task
# def send_subscription_suspended_email(organization_id):
#     """Send email notification for suspended organization"""
#     try:
#         org = Organization.objects.get(id=organization_id)
#
#         # TODO: Implement email sending
#         print(f"Sent suspension notification to {
#               org.name} ({org.contact_email})")
#         return True
#
#     except Organization.DoesNotExist:
#         return False
#
#
# @shared_task
# def auto_renew_subscriptions():
#     """
#     Automatically renew subscriptions with auto_renew enabled
#     Run this task daily
#     """
#     now = timezone.now()
#     tomorrow = now + timedelta(days=1)
#
#     # Find organizations with auto_renew enabled expiring tomorrow
#     organizations = Organization.objects.filter(
#         auto_renew=True,
#         subscription_status='active',
#         subscription_end_date__date=tomorrow.date()
#     )
#
#     renewed_count = 0
#
#     for org in organizations:
#         try:
#             SubscriptionService.renew_subscription(
#                 organization=org,
#                 performed_by_email='system@auto'
#             )
#             renewed_count += 1
#             print(f"Auto-renewed subscription for {org.name}")
#         except Exception as e:
#             print(f"Failed to auto-renew for {org.name}: {str(e)}")
#
#     return {
#         'eligible': organizations.count(),
#         'renewed': renewed_count,
#     }
#
#
# @shared_task
# def cleanup_expired_sessions(organization_id):
#     """
#     Log out all users when subscription expires
#     This should be called when a subscription is expired/suspended
#     """
#     try:
#         from django.contrib.sessions.models import Session
#         from accounts.models import User  # Adjust import based on your user model
#
#         org = Organization.objects.get(id=organization_id)
#
#         # Get all users of this organization
#         # This depends on your user-organization relationship
#         # Example:
#         # users = User.objects.filter(organization_memberships__organization=org)
#
#         # For now, this is a placeholder
#         # You'll need to implement based on your membership model
#
#         print(f"Cleaned up sessions for {org.name}")
#         return True
#
#     except Organization.DoesNotExist:
#         return False
