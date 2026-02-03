from rest_framework import serializers
from .models import Organization
from ..subscriptions.models import SubscriptionPlan


class OrganizationRegisterSerializer(serializers.Serializer):
    """
    Serializer for organization registration
    Handles both user self-registration and admin creation
    """
    # Organization fields
    organization_name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Name of the organization"
    )
    organization_schema_name = serializers.SlugField(
        max_length=100,
        required=True,
        help_text="Unique schema name (e.g., 'acme')"
    )
#    organization_domain_name = serializers.CharField(
#        unique=True,
#        max_length=100,
#        help_text="Domain name of the organization"
#    )
    contact_email = serializers.EmailField(
        required=True,
        help_text="Organization contact email"
    )

    contact_phone = serializers.IntegerField(
        required=False,
        # allow_blank=True,
        help_text="Organization contact phone"
    )

    # Admin user fields
    username = serializers.CharField(
        max_length=150,
        required=True,
        help_text="Admin username"
    )
    email = serializers.EmailField(
        required=True,
        help_text="Admin email"
    )

    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True
    )
    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True
    )

    # Subscription plan field
    slug = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Slug field of subscription plan (optional for admin, defaults to trial plan)"
    )

    is_superuser = serializers.BooleanField(
        default=False,
    )
    is_tenant_admin = serializers.BooleanField(
        default=False,
    )
    is_staff = serializers.BooleanField(
        default=False,
    )

    class Meta:
        model = Organization
        extra_kwargs = {
            'contact_phone': {
                'help_text': 'Enter a 10-digit phone number.',
                'error_messages': {
                    'invalid': 'Ensure this value has exactly 10 digits.'
                }
            }
        }

    def validate_organization_schema_name(self, value):
        """Ensure schema name is unique"""
        if Organization.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError(
                "An organization with this schema name already exists."
            )
        return value

    def validate_slug(self, value):
        """Validate that plan exists and is active"""
        if value is not None:
            try:
                SubscriptionPlan.objects.get(
                    slug=value,
                    is_active=True,
                    is_public=True
                )
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError(
                    "Invalid plan ID or plan is not available."
                )
        return value

    def validate(self, attrs):
        """
        Additional validation
        Require plan_id for non-admin users
        """
        request = self.context.get('request')

        # If not admin and no plan selected, require plan
        if request and not request.user.is_staff:
            if not attrs.get('slug'):
                raise serializers.ValidationError({
                    'plan_id': 'Plan selection is required for registration.'
                })

        return attrs
