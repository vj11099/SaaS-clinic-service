from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User
from rest_framework import serializers, validators


class RegisterSerializer(serializers.ModelSerializer):
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
        }

    def create(self, validated_data):
        return super().create(validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        # Create the standard token
        token = super().get_token(user)

        # Add custom claims (data embedded inside the encrypted token)
        token['username'] = user.username
        token['email'] = user.email

        if user.tenant:
            token['org_id'] = user.tenant.id
            token['org_name'] = user.tenant.name

        return token

    def validate(self, attrs):
        # Standard validation (checks password)
        data = super().validate(attrs)

        # Add extra data to the JSON response (returned alongside the token)
        data['user_id'] = self.user.id
        data['organization'] = self.user.tenant.name if self.user.tenant else None

        return data


class UserSerializer(serializers.ModelSerializer):
    manager_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(
        source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'date_of_birth',
        )
