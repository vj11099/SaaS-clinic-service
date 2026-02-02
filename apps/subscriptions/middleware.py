"""
Subscription Middleware
subscriptions/middleware.py

Middleware to enforce subscription limits and check status
"""
# from django.utils import timezone
from django.http import JsonResponse
from django.urls import resolve
from rest_framework import status


class SubscriptionEnforcementMiddleware:
    """
    Middleware to enforce subscription limits

    Add to MIDDLEWARE in settings.py:
    MIDDLEWARE = [
        ...
        'subscriptions.middleware.SubscriptionEnforcementMiddleware',
    ]
    """

    # Endpoints that should be accessible even with expired subscription
    EXEMPT_PATHS = [
        'subscriptions:plans',
        'subscriptions:current',
        'subscriptions:subscribe',
        'subscriptions:renew',
        'subscriptions:history',
        'auth:login',
        'auth:logout',
        'auth:register',
        'auth:verify',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for non-API requests or exempt paths
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Check if path is exempt
        if self._is_exempt_path(request):
            return self.get_response(request)

        # Get organization from request
        organization = getattr(request, 'tenant', None) or getattr(
            request, 'organization', None)

        if organization:
            # Check subscription status
            if not organization.is_subscription_active():
                return JsonResponse({
                    'error': 'Subscription expired',
                    'detail': 'Your subscription has expired. Please renew to continue.',
                    'subscription_status': organization.subscription_status,
                    'expired_at': organization.subscription_end_date or organization.trial_end_date,
                }, status=status.HTTP_402_PAYMENT_REQUIRED)

            # Check if organization is suspended
            if organization.subscription_status == 'suspended':
                return JsonResponse({
                    'error': 'Account suspended',
                    'detail': 'Your account has been suspended. Please contact support.',
                }, status=status.HTTP_403_FORBIDDEN)

        response = self.get_response(request)
        return response

    def _is_exempt_path(self, request):
        """Check if the request path is exempt from subscription checks"""
        try:
            resolved = resolve(request.path)
            route_name = f"{resolved.namespace}:{
                resolved.url_name}" if resolved.namespace else resolved.url_name
            return route_name in self.EXEMPT_PATHS

        except Exception as e:
            return False


class SubscriptionStatusUpdateMiddleware:
    """
    Middleware to update subscription status on each request
    This ensures status is always current

    Add to MIDDLEWARE in settings.py (before SubscriptionEnforcementMiddleware):
    MIDDLEWARE = [
        ...
        'subscriptions.middleware.SubscriptionStatusUpdateMiddleware',
        'subscriptions.middleware.SubscriptionEnforcementMiddleware',
    ]
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get organization from request
        organization = getattr(request, 'tenant', None) or getattr(
            request, 'organization', None)

        if organization:
            # Update subscription status
            organization.update_subscription_status()

        response = self.get_response(request)
        return response
