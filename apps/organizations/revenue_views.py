from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils.dateparse import parse_datetime

from .revenue_models import Revenue
from .revenue_serializers import (
    RevenueSerializer,
    RevenueSummarySerializer,
    RevenueByPlanSerializer,
    RevenueByTypeSerializer,
    MonthlyRevenueSerializer,
)
from .revenue_services import RevenueService


class RevenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for revenue tracking and analytics

    Endpoints:
        GET /api/revenue/ - List all revenue records
        GET /api/revenue/{id}/ - Get specific revenue record
        GET /api/revenue/summary/ - Get revenue summary
        GET /api/revenue/by_plan/ - Get revenue by plan
        GET /api/revenue/by_type/ - Get revenue by type
        GET /api/revenue/monthly/ - Get monthly revenue
        GET /api/revenue/organization/{org_id}/ - Get org revenue
    """
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        """Filter queryset based on query params"""
        queryset = Revenue.objects.select_related(
            'organization', 'plan'
        ).all()

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)

        if end_date:
            end_date = parse_datetime(end_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)

        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Filter by organization
        org_id = self.request.query_params.get('organization_id')
        if org_id:
            queryset = queryset.filter(organization_id=org_id)

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get revenue summary

        GET /api/revenue/summary/?start_date=2024-01-01&end_date=2024-12-31
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
        if end_date:
            end_date = parse_datetime(end_date)

        summary = RevenueService.get_total_revenue(start_date, end_date)
        serializer = RevenueSummarySerializer(summary)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_plan(self, request):
        """
        Get revenue breakdown by plan

        GET /api/revenue/by_plan/?start_date=2024-01-01&end_date=2024-12-31
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
        if end_date:
            end_date = parse_datetime(end_date)

        data = RevenueService.get_revenue_by_plan(start_date, end_date)
        serializer = RevenueByPlanSerializer(data, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get revenue breakdown by transaction type

        GET /api/revenue/by_type/?start_date=2024-01-01&end_date=2024-12-31
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
        if end_date:
            end_date = parse_datetime(end_date)

        data = RevenueService.get_revenue_by_type(start_date, end_date)
        serializer = RevenueByTypeSerializer(data, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def monthly(self, request):
        """
        Get monthly revenue for the last N months

        GET /api/revenue/monthly/?months=12
        """
        months = request.query_params.get('months', 12)
        try:
            months = int(months)
        except ValueError:
            months = 12

        data = RevenueService.get_monthly_revenue(months)
        serializer = MonthlyRevenueSerializer(data, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='organization/(?P<org_id>[^/.]+)')
    def organization_revenue(self, request, org_id=None):
        """
        Get revenue for a specific organization

        GET /api/revenue/organization/{org_id}/?start_date=2024-01-01
        """
        from apps.organizations.models import Organization

        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
        if end_date:
            end_date = parse_datetime(end_date)

        result = RevenueService.get_organization_revenue(
            organization, start_date, end_date
        )

        transactions = RevenueSerializer(
            result['transactions'][:50], many=True
        ).data

        return Response({
            'organization': {
                'id': organization.id,
                'name': organization.name,
            },
            'total_revenue': result['total_revenue'],
            'transaction_count': result['transaction_count'],
            'recent_transactions': transactions,
        })
