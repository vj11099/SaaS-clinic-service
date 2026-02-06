from django.db import models
from utils.abstract_models import BaseAuditTrailModel


class Permission(BaseAuditTrailModel):
    """
    Defines granular permissions for the system
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'permissions'

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

    def __str__(self):
        return self.name

    def has_permission(self, permission_name):
        """Check if role has a specific permission"""
        return self.permissions.filter(
            name=permission_name,
            is_active=True,
            is_deleted=False
        ).exists()

    def get_permissions_list(self):
        """Get list of all permission names"""
        return list(
            self.permissions.filter(
                is_active=True,
                is_deleted=False
            ).values_list('name', flat=True)
        )


class RolePermission(BaseAuditTrailModel):
    """
    Through model for Role-Permission relationship
    Allows for additional metadata like conditions
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    # conditions = models.JSONField(
    #     null=True,
    #     blank=True,
    #     help_text = "Additional conditions for"
    #     "this permission (e.g., {'department': 'sales'})",
    # )

    class Meta:
        db_table = 'role_permissions'
        unique_together = [('role', 'permission')]

    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"


class UserRole(BaseAuditTrailModel):
    """
    User-Role assignment with optional scope
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='role_users'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    # scope = models.JSONField(
    #     null=True,
    #     blank=True,
    #     help_text="Scope limitations (e.g., {'organization_id': 123})"
    # )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_roles'
        unique_together = [('user', 'role')]

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"
