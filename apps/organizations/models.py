from django.utils import timezone
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from datetime import timedelta
from django.core.validators import RegexValidator


class Organization(TenantMixin):
    """
    Tenant model - PUBLIC schema
    Each tenant represents a separate organization/workspace
    """
    SUBSCRIPTION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]

    # Basic Info
    name = models.CharField(max_length=255)
    schema_name = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    # Contact Info
    contact_email = models.EmailField()
    phone_validator = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be exactly 10 digits (e.g., 1234567890)."
    )
    contact_phone = models.CharField(
        null=True,
        blank=True,
        max_length=20,
        validators=[phone_validator],
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Subscription Information
    subscription_plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='organizations'
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES
    )
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    # Member tracking
    current_member_count = models.IntegerField(default=1)  # Owner counts as 1

    # Grace period (days after expiry before suspension)
    grace_period_days = models.IntegerField(default=7)

    # Auto-renewal flag
    auto_renew = models.BooleanField(default=False)

    # Cancellation tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True)

    auto_create_schema = True
    auto_drop_schema = False

    class Meta:
        db_table = 'organizations'
        indexes = [
            models.Index(fields=['subscription_status']),
            models.Index(fields=['subscription_end_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def is_subscription_active(self):
        """Check if subscription is currently active"""
        now = timezone.now()

        # Check paid subscription
        if self.subscription_end_date:
            return now <= self.subscription_end_date

        return False

    def is_subscription_expired(self):
        """Check if subscription has expired"""
        now = timezone.now()

        if self.subscription_end_date:
            return now > self.subscription_end_date

        return False

    def days_until_expiry(self):
        """Get number of days until subscription expires"""
        now = timezone.now()

        expiry_date = (self.subscription_end_date)

        if not expiry_date:
            return None

        delta = expiry_date - now
        return delta.days

    def can_add_member(self):
        """Check if organization can add more members based on plan limits"""
        if not self.subscription_plan:
            return False

        # Check subscription status
        if not self.is_subscription_active():
            return False

        # Check member limit
        if self.subscription_plan.max_members == -1:  # Unlimited
            return True

        return self.current_member_count < self.subscription_plan.max_members

    def get_member_limit(self):
        """Get the member limit from subscription plan"""
        if not self.subscription_plan:
            return 0
        return self.subscription_plan.max_members

    def update_subscription_status(self):
        """
        Update subscription status based on current dates
        This should be called periodically (via cron job or celery task)
        """
        now = timezone.now()

        # Check if in grace period after expiry
        if self.subscription_end_date:
            grace_end = self.subscription_end_date + \
                timedelta(days=self.grace_period_days)

            if now > grace_end:
                self.subscription_status = 'suspended'
                self.is_active = False
            elif now > self.subscription_end_date:
                self.subscription_status = 'expired'

        self.save(update_fields=['subscription_status',
                  'is_active', 'updated_at'])

        return self.subscription_status

    def subscribe(self, plan):
        """Subscribe to a paid plan"""
        now = timezone.now()
        duration_days = plan.get_duration_days()

        self.subscription_plan = plan
        self.subscription_start_date = now
        self.subscription_end_date = now + timedelta(days=duration_days)
        self.subscription_status = 'active'
        self.is_active = True

        self.save()

        return self

    def renew_subscription(self):
        """Renew current subscription"""
        if not self.subscription_plan:
            raise ValueError("No subscription plan to renew")

        duration_days = self.subscription_plan.get_duration_days()

        # If already expired, start from now
        if self.is_subscription_expired():
            start_date = timezone.now()
        else:
            # Extend from current end date
            start_date = self.subscription_end_date

        self.subscription_end_date = start_date + timedelta(days=duration_days)
        self.subscription_status = 'active'
        self.is_active = True

        self.save()

        return self

    def cancel_subscription(self, reason=None):
        """Cancel subscription (will remain active until end date)"""
        self.subscription_status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.auto_renew = False

        self.save()

        return self


class Domain(DomainMixin):
    class Meta:
        db_table = 'organization_domains'

    def __str__(self):
        return self.domain

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
