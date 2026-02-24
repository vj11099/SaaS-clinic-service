# from datetime import timedelta
# from django.utils import timezone
# from ..organizations.models import Organization
from django.utils import timezone
from django.db import transaction
from .models import SubscriptionPlan, SubscriptionHistory
from ..organizations.revenue_services import RevenueService


class SubscriptionService:
    """Service class to handle subscription operations"""

    @staticmethod
    def get_available_plans():
        """Get all publicly available subscription plans"""
        return SubscriptionPlan.objects.filter(
            is_active=True,
            is_public=True
        ).order_by('sort_order', 'price')

    @staticmethod
    def get_plan_by_slug(slug):
        """Get a specific plan by slug"""
        try:
            return SubscriptionPlan.objects.get(
                slug=slug,
                is_active=True,
                is_public=True
            )
        except SubscriptionPlan.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def subscribe(organization, plan, performed_by_email, performed_by_user=None):
        """
        Subscribe an organization to a paid plan and record revenue

        Args:
            organization: Organization instance
            plan: SubscriptionPlan instance
            performed_by_email: Email of user performing the action
            performed_by_user: User instance (optional, for member profile check)

        Returns:
            Organization instance
        """

        # Check member limit
        if not plan.can_accommodate_members(organization.current_member_count):
            raise ValueError(
                f"Current member count ({organization.current_member_count}) "
                f"exceeds plan limit ({plan.max_members})"
            )

        previous_plan = organization.subscription_plan

        # Subscribe organization
        organization.subscribe(plan)

        # Determine action type
        if previous_plan:
            if plan.price > previous_plan.price:
                action = 'upgraded'
                transaction_type = 'upgrade'
                notes = f"Upgraded from {previous_plan.name} to {plan.name}"
            elif plan.price < previous_plan.price:
                action = 'downgraded'
                transaction_type = 'subscription'
                notes = f"Downgraded from {previous_plan.name} to {plan.name}"
            else:
                action = 'subscribed'
                transaction_type = 'subscription'
                notes = f"Changed to {plan.name}"
        else:
            action = 'subscribed'
            transaction_type = 'subscription'
            notes = f"Subscribed to {plan.name}"

        # Create history record
        history = SubscriptionHistory.objects.create(
            organization=organization,
            plan=plan,
            previous_plan=previous_plan,
            action=action,
            performed_by_email=performed_by_email,
            start_date=organization.subscription_start_date,
            end_date=organization.subscription_end_date,
            metadata={
                'billing_interval': plan.billing_interval,
                'price': str(plan.price),
            },
            notes=notes
        )

        # Record revenue (only if plan has a price > 0)
        if plan.price > 0:
            RevenueService.record_payment(
                organization=organization,
                plan=plan,
                amount=plan.price,
                transaction_type=transaction_type,
                processed_by_email=performed_by_email,
                subscription_history=history,
                notes=notes
            )

        return organization

    @staticmethod
    @transaction.atomic
    def renew_subscription(organization, performed_by_email, new_plan=None, performed_by_user=None):
        """
        Renew an organization's subscription and record revenue

        Args:
            organization: Organization instance
            performed_by_email: Email of user performing the action
            new_plan: Optional new SubscriptionPlan to switch to
            performed_by_user: User instance (optional, for member profile check)

        Returns:
            Organization instance
        """
        if not organization.subscription_plan:
            raise ValueError("Organization has no active subscription plan")

        previous_plan = organization.subscription_plan

        # If switching plans during renewal
        if new_plan and new_plan.id != previous_plan.id:
            # Check member limit
            if not new_plan.can_accommodate_members(organization.current_member_count):
                raise ValueError(
                    f"Current member count ({
                        organization.current_member_count}) "
                    f"exceeds new plan limit ({new_plan.max_members})"
                )
            organization.subscription_plan = new_plan

        # Renew subscription
        organization.renew_subscription()

        # Create history record
        action = 'upgraded' if new_plan and new_plan.price > previous_plan.price else 'renewed'
        transaction_type = 'upgrade' if action == 'upgraded' else 'renewal'

        history = SubscriptionHistory.objects.create(
            organization=organization,
            plan=organization.subscription_plan,
            previous_plan=previous_plan if new_plan else None,
            action=action,
            performed_by_email=performed_by_email,
            start_date=organization.subscription_start_date,
            end_date=organization.subscription_end_date,
            metadata={
                'billing_interval': organization.subscription_plan.billing_interval,
                'price': str(organization.subscription_plan.price),
            },
            notes=f"Renewed subscription to {
                organization.subscription_plan.name}"
        )

        # Record revenue (only if plan has a price > 0)
        if organization.subscription_plan.price > 0:
            RevenueService.record_payment(
                organization=organization,
                plan=organization.subscription_plan,
                amount=organization.subscription_plan.price,
                transaction_type=transaction_type,
                processed_by_email=performed_by_email,
                subscription_history=history,
                notes=f"Renewed subscription to {
                    organization.subscription_plan.name}"
            )

        return organization

    @staticmethod
    @transaction.atomic
    def cancel_subscription(organization, performed_by_email, reason=None, immediate=False, performed_by_user=None):
        """
        Cancel an organization's subscription

        Args:
            organization: Organization instance
            performed_by_email: Email of user performing the action
            reason: Optional cancellation reason
            immediate: If True, suspend immediately; otherwise wait until end date
            performed_by_user: User instance (optional, for member profile check)

        Returns:
            Organization instance
        """
        if not organization.subscription_plan:
            raise ValueError("Organization has no subscription to cancel")

        organization.cancel_subscription(reason)

        # If immediate cancellation, suspend now
        if immediate:
            organization.subscription_end_date = timezone.now()
            organization.subscription_status = 'suspended'
            organization.is_active = False
            organization.save()

        # Create history record
        SubscriptionHistory.objects.create(
            organization=organization,
            plan=organization.subscription_plan,
            action='cancelled',
            performed_by_email=performed_by_email,
            end_date=organization.subscription_end_date,
            metadata={
                'immediate': immediate,
                'will_expire_at': organization.subscription_end_date.isoformat() if not immediate else None,
            },
            notes=reason or "Subscription cancelled"
        )

        return organization

    @staticmethod
    def check_subscription_status(organization):
        """
        Check and update subscription status

        Args:
            organization: Organization instance

        Returns:
            Updated subscription status
        """
        return organization.update_subscription_status()

    @staticmethod
    def get_subscription_history(organization, limit=None):
        """
        Get subscription history for an organization

        Args:
            organization: Organization instance
            limit: Optional limit on number of records

        Returns:
            QuerySet of SubscriptionHistory
        """
        history = organization.subscription_history.all()

        if limit:
            history = history[:limit]

        return history

#    @staticmethod
#    def get_expiring_subscriptions(days_threshold=7):
#        """
#        Get organizations with subscriptions expiring within threshold
#
#        Args:
#            days_threshold: Number of days to check ahead
#
#        Returns:
#            QuerySet of Organization instances
#        """
#        threshold_date = timezone.now() + timedelta(days=days_threshold)
#
#        return Organization.objects.filter(
#            subscription_status='active',
#            subscription_end_date__lte=threshold_date,
#            subscription_end_date__gte=timezone.now()
#        )
#
#    @staticmethod
#    def get_expired_subscriptions():
#        """
#        Get organizations with expired subscriptions
#
#        Returns:
#            QuerySet of Organization instances
#        """
#        now = timezone.now()
#
#        return Organization.objects.filter(
#            subscription_status__in=['active'],
#            subscription_end_date__lt=now
#        )
