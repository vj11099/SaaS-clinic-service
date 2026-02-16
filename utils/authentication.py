from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.db import connection
from utils.caching import cached
# from rich import inspect


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Add schema to token
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['username'] = user.username

        current_schema = connection.schema_name
        if current_schema != 'public':
            token['tenant_schema'] = current_schema

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        data['user'] = {
            'email': self.user.email,
            'username': self.user.username,
        }

        current_schema = connection.schema_name
        if current_schema != 'public':
            data['tenant_schema'] = current_schema

        return data


class TenantJWTAuthentication(JWTAuthentication):
    """
    Enhanced JWT authentication with caching to minimize database calls
    """

    def authenticate(self, request):
        header = self.get_header(request)

        if header is None:
            return None

        # Get the raw JWT token from the request
        raw_token = self.get_raw_token(self.get_header(request))
        if raw_token is None:
            return None

        # Validate token with caching
        validated_token = self.get_validated_token(raw_token)

        # Get user with caching (this is where most DB calls happen)
        user = self._get_cached_user_from_token(validated_token)

        # Validate tenant schema
        self._validate_tenant_schema(validated_token)

        return user, validated_token

    @cached(
        key=lambda self, token: f"jwt_user:{token.get('user_id')}",
        timeout=300,
        tenant_aware=True
    )
    def _get_cached_user_from_token(self, validated_token):
        """
        Cache user lookup from token to avoid DB query on every request.
        This is the main performance optimization.
        """
        return self.get_user(validated_token)

    def _validate_tenant_schema(self, token):
        """Validate that token schema matches current tenant"""
        token_schema = token.get('schema')
        current_schema = connection.schema_name

        # Skip validation for public schema
        if current_schema == 'public':
            return

        if token_schema != current_schema:
            raise AuthenticationFailed(
                f"Token invalid for organization '{current_schema}'. "
                f"Issued for '{token_schema}'."
            )
