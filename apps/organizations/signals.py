# apps/users/signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import connection
from apps.users.models import User
from apps.users.models.roles_and_permissions import Role, UserRole


@receiver(pre_save, sender=User)
def auto_set_superuser_fields(sender, instance, **kwargs):
    """
    Automatically set is_tenant_admin and is_staff to True when is_superuser is True
    Works across all schemas and apps
    """
    if instance.is_superuser:
        instance.is_tenant_admin = True
        instance.is_staff = True


@receiver(post_save, sender=User)
def assign_admin_role_to_superuser(sender, instance, created, **kwargs):
    """
    Automatically assign Admin role to superusers upon creation
    Works across all schemas and apps
    """
    # Only proceed if user is a superuser
    if not instance.is_superuser:
        return

    # For new users or when is_superuser was just set to True
    if created or instance.is_superuser:
        try:
            # Get the Admin role in the current schema
            admin_role = Role.objects.get(
                name='superuser', is_system_role=True
            )

            # Assign role if not already assigned
            UserRole.objects.get_or_create(
                user=instance,
                role=admin_role,
                defaults={
                    'is_active': True,
                    'is_deleted': False,
                }
            )

            # Optional: Log success
            print(f"Assigned superuser role to {
                  instance.email} in schema {connection.schema_name}")

        except Role.DoesNotExist:
            # Log warning - Admin role doesn't exist in this schema
            # import logging
            # logger = logging.getLogger(__name__)
            # logger.warning(
            print(
                f"Superuser role not found in schema '{
                    connection.schema_name}'. "
                f"Cannot assign to superuser {instance.email}. "
                f"Run migrations to create the role."
            )
