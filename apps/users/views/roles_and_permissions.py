from rest_framework import (
    viewsets, serializers, status
)
from django.utils import timezone
from apps.permissions import (
    CanManagePermissions, CanManageRoles, CanAssignRoles)
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Prefetch
from ..models import Role, Permission, RolePermission, UserRole, User
from ..serializers.roles_and_permissions import (
    PermissionSerializer,
    RoleSerializer,
    RoleCreateUpdateSerializer,
    RolePermissionSerializer,
    UserRoleSerializer,
    UserWithRolesSerializer,
    PermissionListSerializer,
    RoleWithPermissionsDetailSerializer
)
from apps.permissions import require_permissions


class PermissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing permissions

    list: Get all permissions
    retrieve: Get a specific permission
    create: Create a new permission
    update: Update a permission (full)
    partial_update: Update a permission (partial)
    destroy: Soft delete a permission
    """

    queryset = Permission.objects.filter(is_deleted=False)
    serializer_class = PermissionSerializer
    permission_classes = [CanManagePermissions]

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('name')

    @require_permissions('permissions.read')
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @require_permissions('permissions.read')
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @require_permissions('permissions.update')
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Soft delete the permission"""
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

    @require_permissions('permissions.delete')
    def destroy(self, request, *args, **kwargs):
        """Override destroy to return proper response"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Permission deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    @require_permissions('permissions.update')
    def restore(self, request, pk=None):
        """Restore a soft-deleted permission"""
        try:
            permission = Permission.objects.get(pk=pk, is_deleted=True)
            permission.is_deleted = False
            permission.is_active = True
            permission.save(
                update_fields=['is_deleted', 'is_active', 'updated_at'])

            serializer = self.get_serializer(permission)
            return Response({
                'message': 'Permission restored successfully',
                'permission': serializer.data
            }, status=status.HTTP_200_OK)
        except Permission.DoesNotExist:
            return Response({
                'error': 'Permission not found or not deleted'
            }, status=status.HTTP_404_NOT_FOUND)


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles

    list: Get all roles
    retrieve: Get a specific role with permissions
    create: Create a new role
    update: Update a role (full)
    partial_update: Update a role (partial)
    destroy: Soft delete a role
    assign_permissions: Assign permissions to a role
    revoke_permissions: Revoke permissions from a role
    """

    permission_classes = [CanManageRoles]

    def get_queryset(self):
        """Get queryset with optimized queries"""
        queryset = Role.objects.filter(is_deleted=False)

        if self.action in ['list', 'retrieve']:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'permissions',
                    queryset=Permission.objects.filter(
                        is_active=True,
                        is_deleted=False,
                        rolepermission__is_active=True,
                        rolepermission__is_deleted=False
                    ).distinct()
                )
            )

        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        include_system = self.request.query_params.get(
            'include_system', 'true')
        if include_system.lower() == 'false':
            queryset = queryset.filter(is_system_role=False)

        return queryset.order_by('name')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""

        if self.action == 'restore':
            return PermissionListSerializer

        if self.action in ['assign_permissions', 'revoke_permissions']:
            return RolePermissionSerializer

        if self.action == 'retrieve':
            return RoleWithPermissionsDetailSerializer

        elif self.action in ['create', 'update', 'partial_update']:
            return RoleCreateUpdateSerializer
        return RoleSerializer

    @require_permissions('roles.read')
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @require_permissions('roles.read')
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Soft delete the role if it's not a system role"""
        if instance.is_system_role:
            raise serializers.ValidationError("Cannot delete system roles.")

        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
        return Response({
            'message': 'Role deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    @require_permissions('roles.update')
    def restore(self, request, pk=None):
        """Restore a soft-deleted role"""
        try:
            role = Role.objects.get(pk=pk, is_deleted=True)
            role.is_deleted = False
            role.is_active = True
            role.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

            serializer = self.get_serializer(role)
            return Response({
                'message': 'Role restored successfully',
                'role': serializer.data
            }, status=status.HTTP_200_OK)
        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found or not deleted'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='assign-permissions')
    @require_permissions('roles.update', 'permissions.update')
    def assign_permissions(self, request):
        """
        Assign permissions to a role
        Body: {
            "role_id": 1,
            "permission_ids": [1, 2, 3]
        }
        """
        serializer = RolePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_id = serializer.validated_data['role_id']
        permission_ids = serializer.validated_data['permission_ids']

        role = Role.objects.get(id=role_id, is_deleted=False)
        permissions = Permission.objects.filter(
            id__in=permission_ids,
            is_deleted=False
        )

        if len(permissions) != len(permission_ids):
            found_ids = set(permissions.values_list('id', flat=True))
            missing_ids = set(permission_ids) - found_ids
            raise serializers.ValidationError(
                f"Permissions not found: {
                    ', '.join(map(str, missing_ids))}"
            )

        existing = RolePermission.objects.filter(
            role=role,
            permission__in=permissions
        ).select_related('permission')

        existing_map = {rp.permission_id: rp for rp in existing}

        to_create = []
        to_restore = []

        for permission in permissions:
            rp = existing_map.get(permission.id)
            if rp is None:
                to_create.append(
                    RolePermission(
                        role=role,
                        permission=permission,
                        is_active=True,
                        is_deleted=False
                    )
                )
            elif rp.is_deleted:
                rp.is_deleted = False
                rp.is_active = True
                rp.updated_at = timezone.now()
                to_restore.append(rp)
        try:
            with transaction.atomic():
                if len(to_create) > 0:
                    RolePermission.objects.bulk_create(
                        to_create, ignore_conflicts=False)

                if len(to_restore) > 0:
                    RolePermission.objects.bulk_update(
                        to_restore, fields=['is_deleted', 'is_active', 'updated_at'])

                assigned_count = len(to_create) + len(to_restore)

                return Response({
                    'message': f'{assigned_count} permission(s) assigned to {role.name} successfully',
                }, status=status.HTTP_200_OK)

        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='revoke-permissions')
    @require_permissions('roles.update', 'permissions.update')
    def revoke_permissions(self, request):
        """
        Revoke permissions from a role
        Body: {
            "role_id": 1,
            "permission_ids": [1, 2, 3]
        }
        """
        serializer = RolePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_id = serializer.validated_data['role_id']
        permission_ids = serializer.validated_data['permission_ids']

        try:
            with transaction.atomic():
                role = Role.objects.get(id=role_id, is_deleted=False)

                deleted_count = RolePermission.objects.filter(
                    role=role,
                    permission_id__in=permission_ids,
                    is_deleted=False
                ).update(is_deleted=True, is_active=False)

                return Response({
                    'message': f'{deleted_count} permission(s) revoked from {role.name} successfully',
                }, status=status.HTTP_200_OK)

        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found'
            }, status=status.HTTP_404_NOT_FOUND)


class UserRoleViewSet(viewsets.ViewSet):
    """
    ViewSet for managing user-role assignments

    Available actions:
    - assign_roles: Assign roles to a user
    - revoke_roles: Revoke roles from a user
    - get_user_roles: Get a user with their roles and permissions
    - get_role_users: Get all users assigned to a specific role
    """
    permission_classes = [CanAssignRoles]

    def get_serializer_class(self):
        if self.action in ['assign_roles', 'revoke_roles']:
            return UserRoleSerializer
        return UserWithRolesSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    @action(detail=False, methods=['post'], url_path='assign-roles')
    @require_permissions('roles.update', 'users.update')
    def assign_roles(self, request):
        """
        Assign roles to a user
        """
        serializer = UserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        role_ids = serializer.validated_data['role_ids']

        user = User.objects.get(id=user_id, is_active=True)
        roles = Role.objects.filter(
            id__in=role_ids,
            is_deleted=False,
            is_active=True
        )

        if len(roles) != len(role_ids):
            found_ids = set(roles.values_list('id', flat=True))
            missing_ids = set(role_ids) - found_ids
            raise serializers.ValidationError(
                f"Roles not found: {', '.join(map(str, missing_ids))}"
            )

        existing = UserRole.objects.filter(
            user=user,
            role__in=roles
        ).select_related('role')

        existing_map = {ur.role_id: ur for ur in existing}

        to_create = []
        to_restore = []

        for role in roles:
            ur = existing_map.get(role.id)
            if ur is None:
                to_create.append(
                    UserRole(
                        user=user,
                        role=role,
                        is_active=True,
                        is_deleted=False,
                    )
                )
            elif ur.is_deleted:
                ur.is_deleted = False
                ur.is_active = True
                ur.updated_at = timezone.now()
                to_restore.append(ur)
        try:
            with transaction.atomic():
                if len(to_create) > 0:
                    UserRole.objects.bulk_create(
                        to_create, ignore_conflicts=False)

                if len(to_restore) > 0:
                    UserRole.objects.bulk_update(
                        to_restore, fields=['is_deleted', 'is_active', 'updated_at'])

            assigned_count = len(to_create) + len(to_restore)

            return Response({
                'message': f'{assigned_count} role(s) assigned to {user.username} successfully',
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='revoke-roles')
    @require_permissions('roles.update', 'users.update')
    def revoke_roles(self, request):
        """
        Revoke roles from a user
        """
        serializer = UserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        role_ids = serializer.validated_data['role_ids']

        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id, is_active=True)

                deleted_count = UserRole.objects.filter(
                    user=user,
                    role_id__in=role_ids,
                    is_deleted=False
                ).update(is_deleted=True, is_active=False)

                return Response({
                    'message': f'{deleted_count} role(s) revoked from {user.username} successfully',
                }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    @require_permissions('roles.read', 'users.read')
    def get_user_roles(self, request, user_id=None):
        """
        Get a user with their roles and permissions

        Path parameters:
        - user_id: ID of the user
        """
        try:
            user = User.objects.prefetch_related(
                Prefetch(
                    'roles',
                    queryset=Role.objects.filter(
                        is_active=True,
                        is_deleted=False,
                        # CRITICAL: Use user_roles__ (the related_name from UserRole.role)
                        user_roles__is_active=True,
                        user_roles__is_deleted=False
                    ).prefetch_related(
                        Prefetch(
                            'permissions',
                            queryset=Permission.objects.filter(
                                is_active=True,
                                is_deleted=False,
                                rolepermission__is_active=True,
                                rolepermission__is_deleted=False
                            ).distinct()
                        )
                    ).distinct()
                )
            ).get(id=user_id, is_active=True)

            serializer = UserWithRolesSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(
        detail=False,
        methods=['get'],
        url_path='role/(?P<role_id>[^/.]+)/users'
    )
    @require_permissions('roles.read', 'users.read')
    def get_role_users(self, request, role_id=None):
        """
        Get all users assigned to a specific role

        Path parameters:
        - role_id: ID of the role
        """
        try:
            role = Role.objects.get(id=role_id, is_deleted=False)

            # Query users through the UserRole table
            # Use user_roles (the related_name from UserRole.user field)
            users = User.objects.filter(
                user_roles__role=role,
                user_roles__is_deleted=False,
                user_roles__is_active=True,
                is_active=True
            ).distinct().prefetch_related(
                Prefetch(
                    'roles',
                    queryset=Role.objects.filter(
                        is_active=True,
                        is_deleted=False,
                        # CRITICAL: Use user_roles__ (the related_name from UserRole.role)
                        # NOT userrole__ (lowercase) - Django is case-sensitive!
                        user_roles__is_active=True,
                        user_roles__is_deleted=False
                    ).prefetch_related(
                        Prefetch(
                            'permissions',
                            queryset=Permission.objects.filter(
                                is_active=True,
                                is_deleted=False,
                                rolepermission__is_active=True,
                                rolepermission__is_deleted=False
                            ).distinct()
                        )
                    ).distinct()
                )
            )

            serializer = UserWithRolesSerializer(users, many=True)

            return Response(
                {
                    'role': {
                        'id': role.id,
                        'name': role.name,
                        'description': role.description
                    },
                    'users': serializer.data,
                    'count': users.count()
                },
                status=status.HTTP_200_OK
            )

        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found'
            }, status=status.HTTP_404_NOT_FOUND)
