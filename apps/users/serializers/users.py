from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from ..models import User
from rest_framework import serializers, validators
from django.contrib.auth.password_validation import validate_password


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
    @classmethod
    def get_token(cls, user):
        # Create the standard token
        token = super().get_token(user)

        token['username'] = user.username
        token['email'] = user.email

        return token

    def validate(self, attrs):
        # Standard validation (checks password)
        data = super().validate(attrs)
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
