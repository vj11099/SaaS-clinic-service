# subscriptions/middleware.py

from django.http import JsonResponse
from django.contrib.auth import logout


class SubscriptionCheckMiddleware:
    """
    Middleware to check subscription status and restrict access
    """

    # Paths that don't require subscription check
    EXEMPT_PATHS = [
        '/api/auth/login/',
        '/api/auth/logout/',
        '/api/plans/',
        '/api/subscription/status/',
        '/api/subscription/subscribe/',
        '/admin/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for exempt paths
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            return self.get_response(request)

        # Skip if on public schema or no organization
        if not hasattr(request, 'organization') or request.organization.schema_name == 'public':
            return self.get_response(request)

        # Get organization from request
        organization = request.organization

        # Check subscription status
        subscription_status = organization.get_subscription_status()

        # Handle different statuses
        if subscription_status['status'] == 'expired':
            # Subscription has expired and grace period is over
            if request.user.is_authenticated:
                logout(request)

            return JsonResponse({
                'error': 'subscription_expired',
                'message': 'Your subscription has expired. Please renew to continue using the service.',
                'status': subscription_status
            }, status=402)  # 402 Payment Required

        elif subscription_status['status'] == 'trial_expired':
            # Trial has expired
            if request.user.is_authenticated:
                logout(request)

            return JsonResponse({
                'error': 'trial_expired',
                'message': 'Your trial period has ended. Please subscribe to a plan to continue.',
                'status': subscription_status
            }, status=402)

        elif subscription_status['status'] == 'grace_period':
            # In grace period - allow access but add warning header
            response = self.get_response(request)
            response['X-Subscription-Warning'] = 'grace_period'
            response['X-Days-Remaining'] = str(
                subscription_status['days_remaining'])
            return response

        elif subscription_status['status'] == 'no_subscription':
            # No subscription at all
            if request.user.is_authenticated:
                logout(request)

            return JsonResponse({
                'error': 'no_subscription',
                'message': 'No active subscription found. Please subscribe to a plan.',
                'status': subscription_status
            }, status=402)

        # Subscription is active - continue normally
        return self.get_response(request)


class MemberLimitMiddleware:
    """
    Middleware to check member limits before allowing member addition
    """

    MEMBER_CREATION_PATHS = [
        '/api/members/',
        '/api/members/invite/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check for POST requests to member creation endpoints
        if request.method == 'POST' and any(
            request.path.startswith(path) for path in self.MEMBER_CREATION_PATHS
        ):
            if hasattr(request, 'organization') and request.organization.schema_name != 'public':
                organization = request.organization

                if not organization.can_add_member():
                    return JsonResponse({
                        'error': 'member_limit_reached',
                        'message': f'Your current plan allows maximum {organization.subscription_plan.max_members} members. Please upgrade to add more.',
                        'current_count': organization.current_member_count,
                        'max_allowed': organization.subscription_plan.max_members
                    }, status=403)

        return self.get_response(request)
