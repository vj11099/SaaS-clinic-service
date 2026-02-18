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
    if not instance.is_superuser:
        return

    # Don't run during migrations
    from django.db import connection
    if connection.in_atomic_block:
        try:
            from django.test.utils import CaptureQueriesContext
        except ImportError:
            pass

    # Better approach: check if tables exist first
    if 'users_userrole' not in connection.introspection.table_names():
        return
    if 'users_role' not in connection.introspection.table_names():
        return

    if created:
        try:
            admin_role = Role.objects.get(
                name='superuser', is_system_role=True)
            UserRole.objects.get_or_create(
                user=instance,
                role=admin_role,
                defaults={'is_active': True, 'is_deleted': False}
            )
        except Role.DoesNotExist:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Superuser role not found in schema '{
                    connection.schema_name}'. "
                f"Cannot assign to superuser {instance.email}."
            )
            # Don't raise here — let org creation succeed
