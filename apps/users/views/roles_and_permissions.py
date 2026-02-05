from rest_framework import (
    viewsets, serializers, status, permissions as drf_permissions
)
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
    RoleWithPermissionsDetailSerializer
)


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
    permission_classes = [drf_permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Search by name or description
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        return queryset.order_by('name')

    def perform_destroy(self, instance):
        """Soft delete the permission"""
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

    @action(detail=True, methods=['post'])
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
    remove_permissions: Remove permissions from a role
    assign_users: Assign users to a role
    remove_users: Remove users from a role
    """
    permission_classes = [drf_permissions.IsAuthenticated]

    def get_queryset(self):
        """Get queryset with optimized queries"""
        queryset = Role.objects.filter(is_deleted=False)

        # Prefetch permissions for list/retrieve
        if self.action in ['list', 'retrieve']:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'permissions',
                    queryset=Permission.objects.filter(
                        is_active=True,
                        is_deleted=False
                    )
                )
            )

        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Search by name or description
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        # Filter system roles
        include_system = self.request.query_params.get(
            'include_system', 'true')
        if include_system.lower() == 'false':
            queryset = queryset.filter(is_system_role=False)

        return queryset.order_by('name')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return RoleWithPermissionsDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return RoleCreateUpdateSerializer
        return RoleSerializer

    def perform_destroy(self, instance):
        """Soft delete the role if it's not a system role"""
        if instance.is_system_role:
            raise serializers.ValidationError("Cannot delete system roles.")

        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

    @action(detail=True, methods=['post'])
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

        try:
            with transaction.atomic():
                role = Role.objects.get(id=role_id, is_deleted=False)
                permissions = Permission.objects.filter(
                    id__in=permission_ids,
                    is_deleted=False
                )

                # Create RolePermission entries
                role_permissions = []
                for permission in permissions:
                    role_perm, created = RolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                        defaults={'is_active': True, 'is_deleted': False}
                    )
                    if not created and role_perm.is_deleted:
                        # Restore if previously deleted
                        role_perm.is_deleted = False
                        role_perm.is_active = True
                        role_perm.save(
                            update_fields=['is_deleted', 'is_active', 'updated_at'])
                    role_permissions.append(role_perm)

                # Refresh role to get updated permissions
                role.refresh_from_db()
                serializer = RoleWithPermissionsDetailSerializer(role)

                return Response({
                    'message': f'{len(permissions)} permission(s) assigned to role successfully',
                    'role': serializer.data
                }, status=status.HTTP_200_OK)

        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='remove-permissions')
    def remove_permissions(self, request):
        """
        Remove permissions from a role
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

                # Soft delete RolePermission entries
                deleted_count = RolePermission.objects.filter(
                    role=role,
                    permission_id__in=permission_ids,
                    is_deleted=False
                ).update(is_deleted=True, is_active=False)

                # Refresh role to get updated permissions
                role.refresh_from_db()
                serializer = RoleWithPermissionsDetailSerializer(role)

                return Response({
                    'message': f'{deleted_count} permission(s) removed from role successfully',
                    'role': serializer.data
                }, status=status.HTTP_200_OK)

        except Role.DoesNotExist:
            return Response({
                'error': 'Role not found'
            }, status=status.HTTP_404_NOT_FOUND)


class UserRoleViewSet(viewsets.ViewSet):
    """
    ViewSet for managing user-role assignments
    """
    permission_classes = [drf_permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='assign-roles')
    def assign_roles(self, request):
        """
        Assign roles to a user
        Body: {
            "user_id": 1,
            "role_ids": [1, 2, 3]
        }
        """
        serializer = UserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        role_ids = serializer.validated_data['role_ids']

        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id, is_active=True)
                roles = Role.objects.filter(
                    id__in=role_ids,
                    is_deleted=False,
                    is_active=True
                )

                # Create UserRole entries
                user_roles = []
                for role in roles:
                    user_role, created = UserRole.objects.get_or_create(
                        user=user,
                        role=role,
                        defaults={'is_active': True, 'is_deleted': False}
                    )
                    if not created and user_role.is_deleted:
                        # Restore if previously deleted
                        user_role.is_deleted = False
                        user_role.is_active = True
                        user_role.save(
                            update_fields=['is_deleted', 'is_active', 'updated_at'])
                    user_roles.append(user_role)

                # Refresh user to get updated roles
                user.refresh_from_db()
                serializer = UserWithRolesSerializer(user)

                return Response({
                    'message': f'{len(roles)} role(s) assigned to user successfully',
                    'user': serializer.data
                }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='remove-roles')
    def remove_roles(self, request):
        """
        Remove roles from a user
        Body: {
            "user_id": 1,
            "role_ids": [1, 2, 3]
        }
        """
        serializer = UserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        role_ids = serializer.validated_data['role_ids']

        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id, is_active=True)

                # Soft delete UserRole entries
                deleted_count = UserRole.objects.filter(
                    user=user,
                    role_id__in=role_ids,
                    is_deleted=False
                ).update(is_deleted=True, is_active=False)

                # Refresh user to get updated roles
                user.refresh_from_db()
                serializer = UserWithRolesSerializer(user)

                return Response({
                    'message': f'{deleted_count} role(s) removed from user successfully',
                    'user': serializer.data
                }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def get_user_roles(self, request, user_id=None):
        """Get a user with their roles and permissions"""
        try:
            user = User.objects.prefetch_related(
                Prefetch(
                    'roles',
                    queryset=Role.objects.filter(
                        is_active=True,
                        is_deleted=False
                    ).prefetch_related(
                        Prefetch(
                            'permissions',
                            queryset=Permission.objects.filter(
                                is_active=True,
                                is_deleted=False
                            )
                        )
                    )
                )
            ).get(id=user_id, is_active=True)

            serializer = UserWithRolesSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='role/(?P<role_id>[^/.]+)/users')
    def get_role_users(self, request, role_id=None):
        """Get all users assigned to a specific role"""
        try:
            role = Role.objects.get(id=role_id, is_deleted=False)

            users = User.objects.filter(
                user_roles__role=role,
                user_roles__is_deleted=False,
                is_active=True
            ).distinct()

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
                'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND)
