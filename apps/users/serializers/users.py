from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from ..models import User
from django.db import connection
from rest_framework import serializers, validators
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate


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

        user = authenticate(
            request=self.context.get('request'),
            username=username_or_email,
            password=password
        )

        if user is None:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(
                    request=self.context.get('request'),
                    username=user_obj.username,
                    password=password
                )
            except User.DoesNotExist:
                user = None

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.password_verified and not user.is_active:
            raise serializers.ValidationError(
                "Account disabled or not verified")

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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'date_of_birth',
        )
        extra_kwargs = {
            'phone': {
                'help_text': 'Enter a 10-digit phone number.',
                'error_messages': {
                    'invalid': 'Ensure this value has exactly 10 digits.'
                }
            }
        }
