from rest_framework import serializers
from .models import SubscriptionPlan, SubscriptionHistory
from ..organizations.models import Organization


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plans"""

    duration_days = serializers.IntegerField(
        source='get_duration_days', read_only=True)
    billing_interval_display = serializers.CharField(
        source='get_billing_interval_display',
        read_only=True
    )

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'price',
            'billing_interval',
            'billing_interval_display',
            'duration_days',
            'max_members',
            'features',
            'is_active',
            'is_public',
            'sort_order',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'slug']


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """Lighter serializer for listing plans"""

    duration_days = serializers.IntegerField(
        source='get_duration_days', read_only=True
    )

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'price',
            'billing_interval',
            'duration_days',
            'max_members',
        ]


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """Serializer for subscription history"""

    plan_name = serializers.CharField(source='plan.name', read_only=True)
    previous_plan_name = serializers.CharField(
        source='previous_plan.name',
        read_only=True,
        allow_null=True
    )
    action_display = serializers.CharField(
        source='get_action_display', read_only=True)

    class Meta:
        model = SubscriptionHistory
        fields = [
            'id',
            'plan',
            'plan_name',
            'previous_plan',
            'previous_plan_name',
            'action',
            'action_display',
            'performed_by_email',
            'start_date',
            'end_date',
            'metadata',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class OrganizationSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for organization subscription details
    """

    plan = SubscriptionPlanSerializer(
        source='subscription_plan', read_only=True
    )
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_active = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    can_add_members = serializers.SerializerMethodField()
    member_limit = serializers.IntegerField(
        source='get_member_limit', read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'plan',
            'subscription_status',
            'subscription_start_date',
            'subscription_end_date',
            'current_member_count',
            'member_limit',
            'is_active',
            'is_expired',
            'days_until_expiry',
            'can_add_members',
            'auto_renew',
            'cancelled_at',
        ]
        read_only_fields = [
            'id',
            'subscription_start_date',
            'subscription_end_date',
            'cancelled_at',
        ]

    def get_is_active(self, obj):
        return obj.is_subscription_active()

    def get_is_expired(self, obj):
        return obj.is_subscription_expired()

    def get_can_add_members(self, obj):
        return obj.can_add_member()


class SubscribeSerializer(serializers.Serializer):
    """
    Serializer for subscribing to a plan
    """
    slug = serializers.SlugField(required=True)

    def validate_slug(self, value):
        """Validate that plan exists and is active"""
        try:
            SubscriptionPlan.objects.get(
                slug=value, is_active=True, is_public=True
            )
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid or inactive subscription plan"
            )

        return value

    def validate(self, attrs):
        """Additional validation"""
        plan = SubscriptionPlan.objects.get(slug=attrs['slug'])
        organization = self.context.get('organization')

        # Check if organization can accommodate current members
        if not plan.can_accommodate_members(organization.current_member_count):
            raise serializers.ValidationError(
                f"Your current member count ({
                    organization.current_member_count}) "
                f"exceeds the limit for this plan ({plan.max_members})"
            )

        return attrs


class CancelSubscriptionSerializer(serializers.Serializer):
    """Serializer for cancelling subscription"""

    reason = serializers.CharField(required=False, allow_blank=True)
    immediate = serializers.BooleanField(default=False)


class RenewSubscriptionSerializer(serializers.Serializer):
    """Serializer for renewing subscription"""

    slug = serializers.SlugField(required=False)

    def validate_plan_id(self, value):
        """Validate that plan exists and is active"""
        if value:
            try:
                SubscriptionPlan.objects.get(
                    slug=value, is_active=True, is_public=True)
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError(
                    "Invalid or inactive subscription plan")

        return value
