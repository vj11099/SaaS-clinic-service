from ..organizations.models import Organization
from rest_framework import serializers


class OrganizationRegisterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255)
    schema_name = serializers.SlugField(max_length=100)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True)

    class Meta:
        model = Organization
        fields = (
            'name', 'schema_name',
            'contact_email', 'contact_phone',
        )
        extra_kwargs = {
            'name': {'required': True},
            'schema_name': {'required': True},
            'contact_email': {'required': True},
            'contact_phone': {'required': True},
        }

    def validate_schema_name(self, value):
        from .models import Organization
        if Organization.objects.filter(slug=value).exists():
            raise serializers.ValidationError(
                "An organization with this schema already exists."
            )
        return value
