from django.db import models
from utils.abstract_models import BaseAuditTrailModel
from utils.caching import cached, CacheConfig


class Permission(BaseAuditTrailModel):
    """
    Defines granular permissions for the system
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'permissions'
        # OPTIMIZATION: Add index for common queries
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'is_deleted']),
        ]

    def __str__(self):
        return f"{self.name}"


class Role(BaseAuditTrailModel):
    """
    Role model for grouping permissions
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles_permission'
    )
    is_system_role = models.BooleanField(
        default=False  # Cannot be deleted/modified
    )

    class Meta:
        db_table = 'roles'
        # OPTIMIZATION: Add index for common queries
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['is_system_role']),
        ]

    def __str__(self):
        return self.name

    def has_permission(self, permission_name):
        """Check if role has a specific permission"""
        # FIX: Also check the through table
        return self.permissions.filter(
            name=permission_name,
            is_active=True,
            is_deleted=False,
            rolepermission__is_active=True,
            rolepermission__is_deleted=False
        ).exists()

    @cached(CacheConfig.ROLE_PERMISSIONS, timeout=CacheConfig.DEFAULT_TTL)
    def get_permissions_list(self):
        """
        Get list of all permission names for this role.

        This method is now cached and will be automatically invalidated when:
        - The role's permissions are changed (via RolePermission signals)
        - The role itself is modified (via Role signals)
        """
        # FIX: Also check the through table
        # OPTIMIZATION: Use values_list directly for minimal query
        return list(
            self.permissions.filter(
                is_active=True,
                is_deleted=False,
                rolepermission__is_active=True,
                rolepermission__is_deleted=False
            ).values_list('name', flat=True).distinct()
        )


class RolePermission(BaseAuditTrailModel):
    """
    Through model for Role-Permission relationship
    Allows for additional metadata like conditions
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = 'role_permissions'
        unique_together = [('role', 'permission')]
        # FIX & OPTIMIZATION: Add indexes for soft-delete queries
        indexes = [
            models.Index(fields=['role', 'is_deleted', 'is_active']),
            models.Index(fields=['permission', 'is_deleted', 'is_active']),
            # Composite index for common filtering pattern
            models.Index(fields=['role', 'permission',
                         'is_deleted', 'is_active']),
        ]

    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"


class UserRole(BaseAuditTrailModel):
    """
    User-Role assignment with optional scope
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        # FIX: Changed from 'role_users' to 'user_roles' to match User model expectation
        # The User model has: through='UserRole', so it expects 'user_roles' as related_name
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_roles'
        unique_together = [('user', 'role')]
        # FIX & OPTIMIZATION: Add indexes for soft-delete queries
        indexes = [
            models.Index(fields=['user', 'is_deleted', 'is_active']),
            models.Index(fields=['role', 'is_deleted', 'is_active']),
            # Composite index for common filtering pattern
            models.Index(fields=['user', 'role', 'is_deleted', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"
