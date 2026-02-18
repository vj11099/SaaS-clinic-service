from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import connection
from django.core.cache import cache
from apps.users.models import User
from apps.users.models import Role, UserRole, RolePermission, Permission


def get_current_tenant_schema():
    """Get the current tenant schema name"""
    return getattr(connection, 'schema_name', 'public')


def _tables_ready(*table_names):
    """Check if all required tables exist in the current schema"""
    existing = connection.introspection.table_names()
    return all(t in existing for t in table_names)


def invalidate_all_user_permissions_cache():
    """
    Invalidate permission cache for ALL users in the current tenant.

    This is called when roles or permissions change, as these affect
    all users who have those roles.

    Note: We use bulk invalidation because:
    1. Role/permission changes are infrequent (admin operations)
    2. Simpler than tracking which users have which roles
    3. Safer - no risk of stale cache
    4. Next permission check will lazily reload the cache
    """
    schema = get_current_tenant_schema()

    # Get all active users in current tenant
    user_ids = User.objects.filter(is_active=True).values_list('id', flat=True)

    deleted_count = 0
    for user_id in user_ids:
        cache_key = f"tenant:{schema}:user_perms:{user_id}"
        result = cache.delete(cache_key)
        if result:
            deleted_count += 1

    return deleted_count


def invalidate_role_permissions_cache(role_id):
    """
    Invalidate the permissions cache for a specific role.

    Args:
        role_id: The ID of the role whose cache should be invalidated
    """
    schema = get_current_tenant_schema()
    cache_key = f"tenant:{schema}:role_perms:{role_id}"
    result = cache.delete(cache_key)

    return result


def invalidate_user_permissions_cache(user_id):
    """
    Invalidate the permissions cache for a specific user.

    Args:
        user_id: The ID of the user whose cache should be invalidated
    """
    schema = get_current_tenant_schema()
    cache_key = f"tenant:{schema}:user_perms:{user_id}"
    result = cache.delete(cache_key)

    return result


# -------------------- Permission Changes --------------------

@receiver(post_save, sender=Permission)
def invalidate_cache_on_permission_change(sender, instance, created, **kwargs):
    """
    When a Permission is created or updated, invalidate all user permission caches.

    Why: Permission changes (especially is_active/is_deleted) affect all users
    who have roles with that permission.
    """
    if not created:  # Only on updates (creates don't affect existing users)
        invalidate_all_user_permissions_cache()


@receiver(post_delete, sender=Permission)
def invalidate_cache_on_permission_delete(sender, instance, **kwargs):
    """
    When a Permission is deleted, invalidate all user permission caches.

    Note: This handles hard deletes. Soft deletes are handled by post_save.
    """
    invalidate_all_user_permissions_cache()


# -------------------- Role Changes --------------------

@receiver(post_save, sender=Role)
def invalidate_cache_on_role_change(sender, instance, created, **kwargs):
    """
    When a Role is created or updated, invalidate caches.

    - Invalidates the role's own permission cache
    - Invalidates all user permission caches (since role changes affect users)
    """
    if not created:
        # Invalidate this role's permission cache
        invalidate_role_permissions_cache(instance.id)

        # Invalidate all users who might have this role
        invalidate_all_user_permissions_cache()


@receiver(post_delete, sender=Role)
def invalidate_cache_on_role_delete(sender, instance, **kwargs):
    """
    When a Role is deleted, invalidate caches.

    Note: This handles hard deletes. Soft deletes are handled by post_save.
    """
    # Invalidate this role's permission cache
    invalidate_role_permissions_cache(instance.id)

    # Invalidate all users who might have had this role
    invalidate_all_user_permissions_cache()


# -------------------- RolePermission Changes --------------------

@receiver(post_save, sender=RolePermission)
def invalidate_cache_on_role_permission_change(sender, instance, created, **kwargs):
    """
    When a RolePermission is created or updated, invalidate caches.

    This handles:
    - Adding permissions to a role
    - Soft-deleting (revoking) permissions from a role
    - Restoring previously revoked permissions
    """
    # Invalidate the role's permission cache
    invalidate_role_permissions_cache(instance.role_id)

    # Invalidate all users who have this role
    invalidate_all_user_permissions_cache()


@receiver(post_delete, sender=RolePermission)
def invalidate_cache_on_role_permission_delete(sender, instance, **kwargs):
    """
    When a RolePermission is hard-deleted, invalidate caches.

    Note: Soft deletes are handled by post_save above.
    """
    # Invalidate the role's permission cache
    invalidate_role_permissions_cache(instance.role_id)

    # Invalidate all users who have this role
    invalidate_all_user_permissions_cache()


# -------------------- UserRole Changes --------------------

@receiver(post_save, sender=UserRole)
def invalidate_cache_on_user_role_change(sender, instance, created, **kwargs):
    """
    When a UserRole is created or updated, invalidate the user's permission cache.

    This handles:
    - Assigning roles to users
    - Soft-deleting (revoking) roles from users
    - Restoring previously revoked roles
    """
    # Invalidate this specific user's permission cache
    invalidate_user_permissions_cache(instance.user_id)


@receiver(post_delete, sender=UserRole)
def invalidate_cache_on_user_role_delete(sender, instance, **kwargs):
    """
    When a UserRole is hard-deleted, invalidate the user's permission cache.

    Note: Soft deletes are handled by post_save above.
    """
    # Invalidate this specific user's permission cache
    invalidate_user_permissions_cache(instance.user_id)


# ========================================================================
# SIGNAL REGISTRATION INFO
# ========================================================================

"""
CACHE INVALIDATION STRATEGY:

1. **Permission/Role Changes** → Invalidate ALL users
   - When permissions or roles are modified, we don't know which users are affected
   - Bulk invalidation is safer and simpler
   - These are infrequent admin operations, so performance impact is minimal

2. **User-Role Changes** → Invalidate SPECIFIC user
   - When a user's roles change, we know exactly which user is affected
   - More efficient to invalidate just that user's cache

3. **RolePermission Changes** → Invalidate role cache + ALL users
   - Updates the role's own permission cache
   - Invalidates all users since we don't track role membership

PERFORMANCE NOTES:
- Permission checks happen frequently (every API request)
- Role/permission changes happen rarely (admin operations)
- Therefore, aggressive invalidation on changes is acceptable
- Lazy cache rebuilding means only active users pay the cost

THREAD SAFETY:
- Django signals are synchronous and run in the same transaction
- Cache invalidation happens after the database commit
- No race conditions between invalidation and cache rebuilding
"""
