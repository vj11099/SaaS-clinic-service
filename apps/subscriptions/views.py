from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import SubscriptionPlan, SubscriptionHistory
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionPlanListSerializer,
    SubscriptionHistorySerializer,
    OrganizationSubscriptionSerializer,
    SubscribeSerializer,
    CancelSubscriptionSerializer,
    RenewSubscriptionSerializer,
)
from .services import SubscriptionService
from .permissions import IsOrganizationOwnerOrAdmin


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving subscription plans

    Endpoints:
        GET /api/subscriptions/plans/ - List all available plans
        GET /api/subscriptions/plans/{slug}/ - Get plan by slug
    """
    queryset = SubscriptionPlan.objects.filter(is_active=True, is_public=True)
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return SubscriptionPlanListSerializer
        return SubscriptionPlanSerializer

    def get_queryset(self):
        return SubscriptionService.get_available_plans()


class OrganizationSubscriptionViewSet(viewsets.GenericViewSet):
    """
    ViewSet for managing organization subscriptions

    Endpoints:
        GET /api/subscriptions/current/ - Get current subscription details
        POST /api/subscriptions/subscribe/ - Subscribe to a plan
        POST /api/subscriptions/renew/ - Renew subscription
        POST /api/subscriptions/cancel/ - Cancel subscription
        GET /api/subscriptions/history/ - Get subscription history
        POST /api/subscriptions/check-status/ - Check and update subscription status
    """
    permission_classes = [IsAuthenticated, IsOrganizationOwnerOrAdmin]

    def get_serializer_class(self):
        if self.action == 'subscribe':
            return SubscribeSerializer
        elif self.action == 'cancel':
            return CancelSubscriptionSerializer
        elif self.action == 'renew':
            return RenewSubscriptionSerializer
        elif self.action == 'history':
            return SubscriptionHistorySerializer
        return OrganizationSubscriptionSerializer

    def get_organization(self):
        """Get the current organization from request"""
        # This assumes you have middleware that sets request.tenant
        # or request.organization based on the current tenant
        return getattr(self.request, 'tenant', None) or getattr(self.request, 'organization', None)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get current subscription details for the organization

        GET /api/subscriptions/current/
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrganizationSubscriptionSerializer(organization)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """
        Subscribe to a new plan

        POST /api/subscriptions/subscribe/
        Body: {
            "plan_id": 1,
            "start_trial": false
        }
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SubscribeSerializer(
            data=request.data,
            context={'organization': organization}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        plan_id = serializer.validated_data['plan_id']
        start_trial = serializer.validated_data.get('start_trial', False)

        try:
            plan = SubscriptionService.get_plan_by_id(plan_id)

            if not plan:
                return Response(
                    {'error': 'Plan not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Start trial or subscribe
            if start_trial:
                organization = SubscriptionService.start_trial(
                    organization=organization,
                    plan=plan,
                    performed_by_email=request.user.email
                )
                message = f"Trial started successfully for {plan.name}"
            else:
                organization = SubscriptionService.subscribe(
                    organization=organization,
                    plan=plan,
                    performed_by_email=request.user.email
                )
                message = f"Successfully subscribed to {plan.name}"

            org_serializer = OrganizationSubscriptionSerializer(organization)

            return Response({
                'message': message,
                'subscription': org_serializer.data
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def renew(self, request):
        """
        Renew current subscription

        POST /api/subscriptions/renew/
        Body: {
            "plan_id": 2  // Optional - to switch plans during renewal
        }
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RenewSubscriptionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        plan_id = serializer.validated_data.get('plan_id')
        new_plan = None

        if plan_id:
            new_plan = SubscriptionService.get_plan_by_id(plan_id)
            if not new_plan:
                return Response(
                    {'error': 'Plan not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            organization = SubscriptionService.renew_subscription(
                organization=organization,
                performed_by_email=request.user.email,
                new_plan=new_plan
            )

            org_serializer = OrganizationSubscriptionSerializer(organization)

            return Response({
                'message': 'Subscription renewed successfully',
                'subscription': org_serializer.data
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """
        Cancel current subscription

        POST /api/subscriptions/cancel/
        Body: {
            "reason": "Too expensive",
            "immediate": false
        }
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CancelSubscriptionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = serializer.validated_data.get('reason')
        immediate = serializer.validated_data.get('immediate', False)

        try:
            organization = SubscriptionService.cancel_subscription(
                organization=organization,
                performed_by_email=request.user.email,
                reason=reason,
                immediate=immediate
            )

            org_serializer = OrganizationSubscriptionSerializer(organization)

            message = 'Subscription cancelled'
            if immediate:
                message += ' immediately'
            else:
                message += f' and will expire on {
                    organization.subscription_end_date.date()}'

            return Response({
                'message': message,
                'subscription': org_serializer.data
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Get subscription history

        GET /api/subscriptions/history/?limit=10
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        limit = request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
            except ValueError:
                limit = None

        history = SubscriptionService.get_subscription_history(
            organization, limit)
        serializer = SubscriptionHistorySerializer(history, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def check_status(self, request):
        """
        Check and update subscription status

        POST /api/subscriptions/check-status/
        """
        organization = self.get_organization()

        if not organization:
            return Response(
                {'error': 'Organization not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = SubscriptionService.check_subscription_status(
            organization)

        org_serializer = OrganizationSubscriptionSerializer(organization)

        return Response({
            'status': new_status,
            'subscription': org_serializer.data
        })
