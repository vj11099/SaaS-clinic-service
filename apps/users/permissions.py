from rest_framework import permissions


class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to verified users.

    Usually used when user wants to change profile or credentials
    """
    message = "Your account is not verified. Please verify your account first."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.password_verified and request.user.is_active
