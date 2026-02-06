# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.db import connection
# from apps.users.models import User
# from apps.users.models.roles_and_permissions import Role, UserRole


# @receiver(post_save, sender=User)
# def assign_permissions_to_superuser_role(sender, instance, created, **kwargs):
#     """
#     Automatically assign Admin role to superusers upon creation
#     Works across all schemas and apps
#     """
#     if not instance.is_superuser:
#         return
#
#     if created or instance.is_superuser:
#         try:
#             admin_role = Role.objects.get(
#                 name='superuser', is_system_role=True
#             )
#
#             UserRole.objects.get_or_create(
#                 user=instance,
#                 role=admin_role,
#                 defaults={
#                     'is_active': True,
#                     'is_deleted': False,
#                 }
#             )
#
#             print(f"Assigned superuser role to {
#                   instance.email} in schema {connection.schema_name}")
#
#         except Role.DoesNotExist:
#             # Log warning - Admin role doesn't exist in this schema
#             # import logging
#             # logger = logging.getLogger(__name__)
#             # logger.warning(
#             print(
#                 f"Superuser role not found in schema '{
#                     connection.schema_name}'. "
#                 f"Cannot assign to superuser {instance.email}. "
#                 f"Run migrations to create the role."
#             )
