from rest_framework import serializers
from ..models import Role, Permission


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""

    class Meta:
        model = Permission
        fields = (
            'id', 'name', 'description', 'is_active',
            'is_deleted', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'is_active', 'is_deleted'
        )
        extra_kwargs = {
            'name': {'required': True},
        }

    def validate_name(self, value):
        """Ensure permission name is unique and not empty"""
        if not value.strip():
            raise serializers.ValidationError(
                "Permission name cannot be empty.")
        return value.strip()


class PermissionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing permissions"""

    class Meta:
        model = Permission
        fields = ('id', 'name', 'description')


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model with nested permissions"""

    permissions = PermissionListSerializer(many=True, read_only=True)
    permission_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            'id', 'name', 'description', 'permissions', 'permission_count',
            'is_system_role', 'is_active', 'is_deleted',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'is_system_role', 'created_at', 'updated_at')
        extra_kwargs = {
            'name': {'required': True},
        }

    def get_permission_count(self, obj):
        """Get count of active permissions"""
        return obj.permissions.filter(is_active=True, is_deleted=False).count()

    def validate_name(self, value):
        """Ensure role name is unique and not empty"""
        if not value.strip():
            raise serializers.ValidationError("Role name cannot be empty.")
        return value.strip()


class RoleListSerializer(serializers.ListSerializer):
    class Meta:
        model = Role
        fields = ('id', 'name', 'description')


class RoleCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating roles without nested permissions"""

    class Meta:
        model = Role
        fields = (
            'id', 'name', 'description'
        )
        read_only_fields = ['id', 'is_active', 'is_deleted']
        extra_kwargs = {
            'name': {'required': True},
        }

    def validate_name(self, value):
        """Ensure role name is unique and not empty"""
        if not value.strip():
            raise serializers.ValidationError("Role name cannot be empty.")
        return value.strip()


class RolePermissionSerializer(serializers.Serializer):
    """Serializer for assigning/removing permissions to/from roles"""

    role_id = serializers.IntegerField(required=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )

    def validate_role_id(self, value):
        """Validate that role exists and is not deleted"""
        try:
            role = Role.objects.get(id=value, is_deleted=False)
            if role.is_system_role:
                raise serializers.ValidationError(
                    "Cannot modify permissions for system roles."
                )
            return value
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role not found.")

    def validate_permission_ids(self, value):
        """Validate that all permissions exist and are not deleted"""
        if not value:
            raise serializers.ValidationError(
                "At least one permission is required."
            )

        existing_permissions = Permission.objects.filter(
            id__in=value,
            is_deleted=False
        ).values_list('id', flat=True)

        invalid_ids = set(value) - set(existing_permissions)
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid permission IDs: {', '.join(map(str, invalid_ids))}"
            )
        return value


class UserRoleSerializer(serializers.Serializer):
    """Serializer for assigning/removing roles to/from users"""

    user_id = serializers.IntegerField(required=True)
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )

    def validate_user_id(self, value):
        """Validate that user exists and is active"""
        from ..models import User
        try:
            User.objects.get(id=value, is_active=True)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found or inactive.")

    def validate_role_ids(self, value):
        """Validate that all roles exist and are not deleted"""
        if not value:
            raise serializers.ValidationError("At least one role is required.")

        existing_roles = Role.objects.filter(
            id__in=value,
            is_deleted=False,
            is_active=True
        ).values_list('id', flat=True)

        invalid_ids = set(value) - set(existing_roles)
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid role IDs: {', '.join(map(str, invalid_ids))}"
            )
        return value


class UserWithRolesSerializer(serializers.ModelSerializer):
    """Serializer for displaying user with their roles"""

    from ..serializers import UserSerializer

    roles = RoleSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        from ..models import User
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'roles', 'permissions'
        )

    def get_permissions(self, obj):
        """Get all permissions from user's roles"""
        return obj.get_all_permissions()


class RoleWithPermissionsDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for role with full permission details"""
    permissions = PermissionSerializer(many=True, read_only=True)
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            'id', 'name', 'description', 'users_count', 'permissions',
            'is_system_role', 'is_active', 'is_deleted',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'is_system_role', 'created_at', 'updated_at')

    def get_users_count(self, obj):
        """Get count of users with this role"""
        return obj.user_roles.filter(
            user__is_active=True,
            is_deleted=False
        ).count()
