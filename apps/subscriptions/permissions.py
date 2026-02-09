"""
Subscription Permissions
subscriptions/permissions.py
"""
from rest_framework import permissions


class IsOrganizationOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is owner or admin of the organization
    """

    def has_permission(self, request, view):
        """Check if user has permission to access organization subscription"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Get organization from request
        # organization = getattr(request, 'tenant', None) or getattr(
        #     request, 'organization', None)

        # if not organization:
        #     return False

        # # Check if user is owner or admin
        # # You'll need to implement this based on your membership model
        # # This is a placeholder implementation
        # return self._is_owner_or_admin(request.user, organization)

    # def _is_owner_or_admin(self, user, organization):
    #     """
    #     Check if user is owner or admin of organization

    #     Implement this based on your membership model
    #     For example:

    #     from memberships.models import Membership

    #     try:
    #         membership = Membership.objects.get(
    #             user=user,
    #             organization=organization
    #         )
    #         return membership.role in ['owner', 'admin']
    #     except Membership.DoesNotExist:
    #         return False
    #     """
    #     # Placeholder - implement based on your membership model
    #     return True


class CanManageSubscription(permissions.BasePermission):
    """
    Permission to check if user can manage subscription
    (owner only, not admins)
    """

    def has_permission(self, request, view):
        """Check if user has permission to manage subscription"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Get organization from request
        organization = getattr(request, 'tenant', None) or getattr(
            request, 'organization', None)

        if not organization:
            return False

        # Check if user is owner
        return self._is_owner(request.user, organization)

    def _is_owner(self, user, organization):
        """
        Check if user is owner of organization

        Implement this based on your membership model
        """
        # Placeholder - implement based on your membership model
        return True


class HasActiveSubscription(permissions.BasePermission):
    """
    Permission to check if organization has an active subscription
    """

    def has_permission(self, request, view):
        """Check if organization has active subscription"""
        # Get organization from request
        organization = getattr(request, 'tenant', None) or getattr(
            request, 'organization', None
        )

        if not organization:
            return False

        return organization.is_subscription_active()

    message = 'Your subscription has expired. Please renew to access this resource.'
