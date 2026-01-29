from django.utils import timezone
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Organization(TenantMixin):
    """
    Tenant model - stored in PUBLIC schema
    Each tenant represents a separate organization/workspace
    """
    name = models.CharField(max_length=255)
    schema_name = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    max_users = models.IntegerField(default=10)

    # Subscription information (stored in public schema for quick access)
    subscription_plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tenants'
    )

    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    is_trial = models.BooleanField(default=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)

    current_member_count = models.IntegerField(default=1)  # Owner counts as 1

    auto_create_schema = True
    auto_drop_schema = False

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name

    def is_subscription_active(self):
        """Check if subscription is currently active"""
        if self.is_trial and self.trial_end_date:
            return timezone.now() <= self.trial_end_date

        if self.subscription_end_date:
            return timezone.now() <= self.subscription_end_date

        return False

    def is_within_grace_period(self):
        """Check if tenant is within grace period after expiration"""
        from django.conf import settings

        grace_days = getattr(settings, 'SUBSCRIPTION_GRACE_PERIOD_DAYS', 7)

        if self.subscription_end_date:
            grace_end = self.subscription_end_date + \
                timezone.timedelta(days=grace_days)
            return timezone.now() <= grace_end

        return False

    def can_add_member(self):
        """Check if tenant can add more members based on subscription"""
        if not self.subscription_plan:
            return False

        if self.subscription_plan.max_members == -1:  # Unlimited
            return True

        return self.current_member_count < self.subscription_plan.max_members

    def get_subscription_status(self):
        """Get current subscription status"""
        now = timezone.now()

        if self.is_trial and self.trial_end_date:
            if now <= self.trial_end_date:
                days_remaining = (self.trial_end_date - now).days
                return {
                    'status': 'trial',
                    'active': True,
                    'days_remaining': days_remaining,
                    'end_date': self.trial_end_date
                }
            else:
                return {
                    'status': 'trial_expired',
                    'active': False,
                    'days_remaining': 0
                }

        if self.subscription_end_date:
            if now <= self.subscription_end_date:
                days_remaining = (self.subscription_end_date - now).days
                return {
                    'status': 'active',
                    'active': True,
                    'days_remaining': days_remaining,
                    'end_date': self.subscription_end_date,
                    'plan': (self.subscription_plan.name if self.subscription_plan else None)
                }
            elif self.is_within_grace_period():
                from django.conf import settings
                grace_days = getattr(
                    settings, 'SUBSCRIPTION_GRACE_PERIOD_DAYS', 7)
                grace_end = self.subscription_end_date + \
                    timezone.timedelta(days=grace_days)
                days_in_grace = (grace_end - now).days

                return {
                    'status': 'grace_period',
                    'active': True,  # Still accessible but with warnings
                    'days_remaining': days_in_grace,
                    'grace_end': grace_end
                }
            else:
                return {
                    'status': 'expired',
                    'active': False,
                    'days_remaining': 0
                }

        return {
            'status': 'no_subscription',
            'active': False
        }


# class Organization(TenantMixin):
#     name = models.CharField(max_length=255)
#     schema_name = models.SlugField(max_length=100, unique=True)
#     description = models.TextField(blank=True, null=True)
#
#     contact_email = models.EmailField()
#     contact_phone = models.CharField(max_length=20, blank=True, null=True)
#
#     is_active = models.BooleanField(default=True)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     max_users = models.IntegerField(default=10)
#
#     class Meta:
#         db_table = 'organizations'
#
#     def __str__(self):
#         return self.name
#
#     auto_create_schema = True


class Domain(DomainMixin):
    class Meta:
        db_table = 'organization_domains'

    def __str__(self):
        return self.domain
