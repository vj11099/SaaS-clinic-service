from rest_framework import permissions
from django.db import connection


class IsOrganizationMember(permissions.BasePermission):
    """
    Allows access only to authenticated, verified users within a tenant.
    """
    message = "Access denied."

    def has_permission(self, request, view):
        if connection.schema_name == 'public':
            self.message = "Please use a valid tenant to perform this action."
            return False

        if not request.user or not request.user.is_authenticated:
            self.message = "You must be logged in to perform this action."
            return False

        if not request.user.is_active:
            self.message = "This user account is inactive."
            return False

        if not getattr(request.user, 'password_verified', False):
            self.message = "Please verify your credentials/password before proceeding."
            return False

        return True
