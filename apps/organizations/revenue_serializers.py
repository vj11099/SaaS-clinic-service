from rest_framework import serializers
from .revenue_models import Revenue


class RevenueSerializer(serializers.ModelSerializer):
    """Serializer for revenue records"""

    organization_name = serializers.CharField(
        source='organization.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display',
        read_only=True
    )

    class Meta:
        model = Revenue
        fields = [
            'id',
            'organization',
            'organization_name',
            'plan',
            'plan_name',
            'amount',
            'transaction_type',
            'transaction_type_display',
            'billing_interval',
            'processed_by_email',
            'notes',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RevenueSummarySerializer(serializers.Serializer):
    """Serializer for revenue summary stats"""

    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    transaction_count = serializers.IntegerField()


class RevenueByPlanSerializer(serializers.Serializer):
    """Serializer for revenue breakdown by plan"""

    plan__name = serializers.CharField()
    plan__slug = serializers.CharField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    count = serializers.IntegerField()


class RevenueByTypeSerializer(serializers.Serializer):
    """Serializer for revenue breakdown by type"""

    transaction_type = serializers.CharField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    count = serializers.IntegerField()


class MonthlyRevenueSerializer(serializers.Serializer):
    """Serializer for monthly revenue data"""

    month = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    count = serializers.IntegerField()
