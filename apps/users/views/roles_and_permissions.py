from rest_framework import (
    viewsets, serializers, status
)
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

    def perform_destroy(self, instance):
        """Soft delete the permission"""
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=['is_deleted', 'is_active', 'updated_at'])

    def destroy(self, request, *args, **kwargs):
        """Override destroy to return proper response"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Permission deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)

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
    revoke_permissions: Revoke permissions from a role
    """

    permission_classes = [CanManageRoles]

    def get_queryset(self):
        """Get queryset with optimized queries"""
        queryset = Role.objects.filter(is_deleted=False)

        if self.action in ['list', 'retrieve']:
            # FIX #1: CRITICAL BUG - Filter through RolePermission table to exclude soft-deleted relationships
            # This was causing revoked permissions to still appear
            queryset = queryset.prefetch_related(
                Prefetch(
                    'permissions',
                    queryset=Permission.objects.filter(
                        is_active=True,
                        is_deleted=False,
                        # CRITICAL: Filter the through table to exclude soft-deleted relationships
                        rolepermission__is_active=True,
                        rolepermission__is_deleted=False
                        # Use distinct to avoid duplicates from through table joins
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

                # FIX #2: Validate that we found all requested permissions
                if len(permissions) != len(permission_ids):
                    found_ids = set(permissions.values_list('id', flat=True))
                    missing_ids = set(permission_ids) - found_ids
                    raise serializers.ValidationError(
                        f"Permissions not found: {
                            ', '.join(map(str, missing_ids))}"
                    )

                assigned_count = 0
                for permission in permissions:
                    role_perm, created = RolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                        defaults={'is_active': True, 'is_deleted': False}
                    )
                    if created:
                        assigned_count += 1
                    elif role_perm.is_deleted:
                        # Restore previously deleted relationship
                        role_perm.is_deleted = False
                        role_perm.is_active = True
                        role_perm.save(
                            update_fields=['is_deleted', 'is_active', 'updated_at'])
                        assigned_count += 1

                # FIX #3: Re-fetch with proper prefetch instead of refresh_from_db()
                # refresh_from_db() doesn't reload M2M relationships properly
                role = Role.objects.prefetch_related(
                    Prefetch(
                        'permissions',
                        queryset=Permission.objects.filter(
                            is_active=True,
                            is_deleted=False,
                            rolepermission__is_active=True,
                            rolepermission__is_deleted=False
                        ).distinct()
                    )
                ).get(id=role_id)

                serializer = RoleWithPermissionsDetailSerializer(role)

                return Response({
                    'message': f'{assigned_count} permission(s) assigned to role successfully',
                    'role': serializer.data
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

                # FIX #4: Re-fetch with proper prefetch instead of refresh_from_db()
                role = Role.objects.prefetch_related(
                    Prefetch(
                        'permissions',
                        queryset=Permission.objects.filter(
                            is_active=True,
                            is_deleted=False,
                            rolepermission__is_active=True,
                            rolepermission__is_deleted=False
                        ).distinct()
                    )
                ).get(id=role_id)

                serializer = RoleWithPermissionsDetailSerializer(role)

                return Response({
                    'message': f'{deleted_count} permission(s) revoked from role successfully',
                    'role': serializer.data
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
    def assign_roles(self, request):
        """
        Assign roles to a user
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

                # Validate that we found all requested roles
                if len(roles) != len(role_ids):
                    found_ids = set(roles.values_list('id', flat=True))
                    missing_ids = set(role_ids) - found_ids
                    raise serializers.ValidationError(
                        f"Roles not found: {', '.join(map(str, missing_ids))}"
                    )

                assigned_count = 0
                for role in roles:
                    user_role, created = UserRole.objects.get_or_create(
                        user=user,
                        role=role,
                        defaults={'is_active': True, 'is_deleted': False}
                    )
                    if created:
                        assigned_count += 1
                    elif user_role.is_deleted:
                        # Restore previously deleted relationship
                        user_role.is_deleted = False
                        user_role.is_active = True
                        user_role.save(
                            update_fields=['is_deleted',
                                           'is_active', 'updated_at']
                        )
                        assigned_count += 1

                # Re-fetch user with proper prefetch
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
                ).get(id=user_id)

                serializer = UserWithRolesSerializer(user)

                return Response({
                    'message': f'{assigned_count} role(s) assigned to user successfully',
                    'user': serializer.data
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

                # Re-fetch user with proper prefetch
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
                ).get(id=user_id)

                serializer = UserWithRolesSerializer(user)

                return Response({
                    'message': f'{deleted_count} role(s) revoked from user successfully',
                    'user': serializer.data
                }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                'error': 'User not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
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
