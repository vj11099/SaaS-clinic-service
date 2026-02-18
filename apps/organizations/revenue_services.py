from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .revenue_models import Revenue


class RevenueService:
    """Service class to handle revenue operations"""

    @staticmethod
    @transaction.atomic
    def record_payment(organization, plan, amount, transaction_type,
                       processed_by_email, subscription_history=None, notes=''):
        """
        Record a payment transaction

        Args:
            organization: Organization instance
            plan: SubscriptionPlan instance
            amount: Decimal amount
            transaction_type: Type of transaction
            processed_by_email: Email of user who processed
            subscription_history: Related SubscriptionHistory instance
            notes: Additional notes

        Returns:
            Revenue instance
        """
        revenue = Revenue.objects.create(
            organization=organization,
            plan=plan,
            amount=amount,
            transaction_type=transaction_type,
            billing_interval=plan.billing_interval,
            processed_by_email=processed_by_email,
            subscription_history=subscription_history,
            notes=notes,
            metadata={
                'plan_name': plan.name,
                'plan_price': str(plan.price),
            }
        )

        return revenue

    @staticmethod
    def get_total_revenue(start_date=None, end_date=None):
        """Get total revenue for a date range"""
        queryset = Revenue.objects.exclude(transaction_type='refund')

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        result = queryset.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )

        return {
            'total_revenue': result['total'] or 0,
            'transaction_count': result['count'] or 0
        }

    @staticmethod
    def get_revenue_by_plan(start_date=None, end_date=None):
        """Get revenue breakdown by plan"""
        queryset = Revenue.objects.exclude(transaction_type='refund')

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        revenue_by_plan = queryset.values(
            'plan__name', 'plan__slug'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        return list(revenue_by_plan)

    @staticmethod
    def get_monthly_revenue(months=12):
        """Get revenue for the last N months"""
        from django.db.models.functions import TruncMonth

        end_date = timezone.now()
        start_date = end_date - timedelta(days=months * 30)

        monthly_revenue = Revenue.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).exclude(
            transaction_type='refund'
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('month')

        return list(monthly_revenue)

    @staticmethod
    def get_organization_revenue(organization, start_date=None, end_date=None):
        """Get revenue for a specific organization"""
        queryset = Revenue.objects.filter(organization=organization)

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        result = queryset.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )

        transactions = queryset.order_by('-created_at')

        return {
            'total_revenue': result['total'] or 0,
            'transaction_count': result['count'] or 0,
            'transactions': transactions
        }
