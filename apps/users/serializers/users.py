from rest_framework.exceptions import PermissionDenied
# from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from ..models import User
from django.db import connection
from rest_framework import serializers, validators
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
# from rich import inspect


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        validators=[validators.UniqueValidator(queryset=User.objects.all())]
    )
    email = serializers.EmailField(
        validators=[validators.UniqueValidator(queryset=User.objects.all())]
    )

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name',
            'last_name', 'phone'
        )
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone': {
                'help_text': 'Enter a 10-digit phone number.',
                'error_messages': {
                    'invalid': 'Ensure this value has exactly 10 digits.'
                }
            }
        }

    def create(self, validated_data):
        return super().create(validated_data)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )


class LoginSerializer(TokenObtainPairSerializer):
    username_field = 'username_or_email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['schema'] = connection.schema_name

        return token

    def validate(self, attrs):
        username_or_email = attrs.get('username_or_email')
        password = attrs.get('password')

        org = connection.tenant

        try:
            user = User.objects.get(username=username_or_email)
            if user is None:
                User.objects.get(email=username_or_email)

        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")

        if (
            org.schema_name != 'public' and
            org.is_subscription_expired() and
            not user.is_superuser
        ):

            if org.is_active:
                self._deactivate_org_users(org)
                self._suspend_org(org)
                org.current_user_count = 1
                org.is_active = False
                org.save()

            raise PermissionDenied(
                "Your organization's subscription has expired. "
                "Please contact admin to regain access."
            )

        try:
            _user = authenticate(
                request=self.context.get('request'),
                username=user.username,
                password=password
            )
        except User.DoesNotExist:
            _user = None

        if not _user:
            raise serializers.ValidationError("Invalid credentials")

        if not _user.password_verified and not _user.is_active:
            raise serializers.ValidationError(
                "Account disabled or not verified"
            )

        refresh = self.get_token(user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'username': user.username,
                'email': user.email
            }
        }

        return data

    def _deactivate_org_users(self, org):
        """
        Bulk deactivate all non-admin users in the current tenant schema.
        """

        users_to_deactivate = User.objects.filter(
            is_active=True,
            is_tenant_admin=False,
            is_superuser=False,
        )

        # Invalidate permission cache for each affected user before deactivating.
        # Your @cached decorator exposes .invalidate() — we use it here so stale
        # permissions don't linger in cache after deactivation.

        # for user in users_to_deactivate:
        #     try:
        #         user.get_all_permissions.invalidate(user)
        #     except Exception:
        #         pass

        # Bulk update — single query, no per-object save() overhead.
        users_to_deactivate.update(is_active=False)

    def _suspend_org(self, org):
        """
        Mark the organization as suspended.
        """
        org.update_subscription_status()


class RestoreUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username')
        read_only_fields = ['id', 'email', 'username']


class SubscriptionAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Extends simplejwt's TokenRefreshSerializer to check
    organization subscription status on every token refresh.

    If the subscription is expired:
        1. Deactivates all non-admin users in the tenant (lazy deactivation)
        2. Suspends the organization
        3. Rejects the refresh request
    """

    def validate(self, attrs):
        data = super().validate(attrs)

        org = connection.tenant

        if org.is_subscription_expired():
            from rest_framework_simplejwt.tokens import AccessToken

            access_token = AccessToken(data['access'])
            user_id = access_token['user_id']

            user = User.objects.get(id=user_id)

            # Superusers bypass subscription checks
            if user.is_superuser:
                return data

            if org.is_active:
                self._deactivate_org_users(org)
                self._suspend_org(org)
                org.current_user_count = 1
                org.is_active = False
                org.save()

            raise PermissionDenied(
                "Your organization's subscription has expired. "
                "Please contact admin to regain access."
            )

        return data

    def _deactivate_org_users(self, org):
        """
        Bulk deactivate all non-admin users in the current tenant schema.
        """

        users_to_deactivate = User.objects.filter(
            is_active=True,
            is_tenant_admin=False,
            is_superuser=False,
        )

        users_to_deactivate.update(is_active=False)

    def _suspend_org(self, org):
        """
        Mark the organization as suspended.
        """
        org.update_subscription_status()
