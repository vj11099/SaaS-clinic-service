from rest_framework import status
from rest_framework.response import Response
from functools import wraps
from rest_framework import permissions


class HasPermission(permissions.BasePermission):
    """
    Custom permission class to check if user has a specific permission.
    Usage in views:
        permission_classes = [HasPermission]
        required_permission = 'users.create'
    """

    message = "Access denied."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            self.message = "You must be logged in to perform this action."
            return False

        required_permission = getattr(view, 'required_permission', None)

        if not required_permission:
            return True

        return request.user.has_permission(required_permission)


class HasAnyPermission(permissions.BasePermission):
    """
    Custom permission class to check if user has any of the specified permissions.
    Usage in views:
        permission_classes = [HasAnyPermission]
        required_permissions = ['users.create', 'users.update']
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        required_permissions = getattr(view, 'required_permissions', None)

        if not required_permissions:
            return True

        return request.user.has_any_permission(required_permissions)


class HasAllPermissions(permissions.BasePermission):
    """
    Custom permission class to check if user has all of the specified permissions.
    Usage in views:
        permission_classes = [HasAllPermissions]
        required_permissions = ['users.create', 'users.delete']
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        required_permissions = getattr(view, 'required_permissions', None)

        if not required_permissions:
            return True

        return request.user.has_all_permissions(required_permissions)


class IsTenantAdmin(permissions.BasePermission):
    """
    Custom permission to only allow tenant admins to access.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_tenant_admin


# class IsSystemRole(permissions.BasePermission):
#     """
#     Custom permission to prevent modification of system roles.
#     Used in object-level permissions.
#     """
#
#     def has_object_permission(self, request, view, obj):
#         if request.method in permissions.READONLY_METHODS:
#             return True
#
#         return not obj.is_system_role


class CanManageRoles(permissions.BasePermission):
    """
    Permission to check if user can manage roles.
    Checks for 'roles.create', 'roles.update', 'roles.delete' permissions.
    """

    permission_map = {
        'GET': None,
        'HEAD': None,
        'OPTIONS': None,
        'POST': 'roles.create',
        'PUT': 'roles.update',
        'PATCH': 'roles.update',
        'DELETE': 'roles.delete',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_tenant_admin:
            return True

        required_permission = self.permission_map.get(request.method)

        if not required_permission:
            return True

        return request.user.has_permission(required_permission)


class CanManagePermissions(permissions.BasePermission):
    """
    Permission to check if user can manage permissions.
    Checks for 'permissions.create', 'permissions.update', 'permissions.delete'.
    """

    permission_map = {
        'GET': None,
        'HEAD': None,
        'OPTIONS': None,
        'POST': 'permissions.create',
        'PUT': 'permissions.update',
        'PATCH': 'permissions.update',
        'DELETE': 'permissions.delete',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_tenant_admin:
            return True

        required_permission = self.permission_map.get(request.method)

        if not required_permission:
            return True

        return request.user.has_permission(required_permission)


class CanAssignRoles(permissions.BasePermission):
    """
    Permission to check if user can assign/remove roles to/from users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_tenant_admin:
            return True

        return request.user.has_permission('users.update')


def require_permissions(*permission_codenames):
    """
    Decorator to require specific permissions for a view or viewset action

    Usage:
        @require_permissions('user.create', 'user.update')
        def create(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'detail': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if request.user.is_superuser:
                return func(self, request, *args, **kwargs)

            if not request.user.has_all_permissions(permission_codenames):
                return Response(
                    {
                        'detail': 'You do not have permission to perform this action',
                        'required_permissions': permission_codenames
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permission_codenames):
    """
    Decorator to require ANY of the specified permissions

    Usage:
        @require_any_permission('user.read', 'user.list')
        def list(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'detail': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if request.user.is_superuser:
                return func(self, request, *args, **kwargs)

            if not request.user.has_any_permission(permission_codenames):
                return Response(
                    {
                        'detail': 'You do not have permission to perform this action',
                        'required_permissions': f"Any of: {permission_codenames}"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_tenant_admin(func):
    """
    Decorator to require tenant admin status

    Usage:
        @require_tenant_admin
        def delete(self, request, pk):
            ...
    """
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not (request.user.is_tenant_admin or request.user.is_superuser):
            return Response(
                {'detail': 'Tenant admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        return func(self, request, *args, **kwargs)
    return wrapper


def check_object_permission(permission_func):
    """
    Decorator for custom object-level permission checks

    Usage:
        def can_edit_user(user, obj):
            return obj.created_by == user or user.is_tenant_admin

        @check_object_permission(can_edit_user)
        def update(self, request, pk):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Get object (assumes pk in kwargs)
            pk = kwargs.get('pk')
            if pk:
                obj = self.get_object()
                if not permission_func(request.user, obj):
                    return Response(
                        {'detail': 'You do not have permission to access this object'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
