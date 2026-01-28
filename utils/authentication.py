from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.db import connection


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
    def authenticate(self, request):
        auth_result = super().authenticate(request)
        if auth_result is None:
            return None

        user, token = auth_result

        token_schema = token.get('schema')
        current_schema = connection.schema_name

        if token_schema != current_schema:
            raise AuthenticationFailed(
                f"Token invalid for organization '{current_schema}'."
                f"Issued for '{token_schema}'."
            )

        return user, token
