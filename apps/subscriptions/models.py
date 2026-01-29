from django.db import models
from django.core.validators import MinValueValidator
from utils.abstract_models import BaseAuditTrailModel


class SubscriptionPlan(BaseAuditTrailModel):
    """
    Subscription model - PUBLIC schema
    Available subscription plans for all tenants
    """
    BILLING_INTERVAL_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    billing_interval = models.CharField(
        max_length=20,
        choices=BILLING_INTERVAL_CHOICES,
        default='monthly'
    )

    # Member limits
    max_members = models.IntegerField(
        help_text="Maximum number of members allowed. Use -1 for unlimited",
        validators=[MinValueValidator(-1)]
    )

    # Features as JSON
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object with feature flags and limits"
    )

    # Visibility
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this plan is publicly available for subscription"
    )

    # Trial configuration
    trial_days = models.IntegerField(
        default=14,
        help_text="Number of trial days for this plan"
    )

    sort_order = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions_plan'
        ordering = ['sort_order', 'price']

    def __str__(self):
        return f"{self.name} ({self.get_billing_interval_display()})"

    def get_duration_days(self):
        """
        Get duration in days based on billing interval
        """
        if self.billing_interval == 'monthly':
            return 30
        elif self.billing_interval == 'yearly':
            return 365
        return 30

    def can_accommodate_members(self, member_count):
        """
        Check if plan can accommodate given number of members
        """
        if self.max_members == -1:  # Unlimited
            return True
        return member_count <= self.max_members


class SubscriptionHistory(models.Model):
    """
    Subscription History model - PUBLIC schema
    Tracks all subscription changes for a tenant
    """
    ACTION_CHOICES = [
        ('subscribed', 'Subscribed'),
        ('upgraded', 'Upgraded'),
        ('downgraded', 'Downgraded'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
        ('reactivated', 'Reactivated'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='subscription_history'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    previous_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='previous_subscriptions'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # Who performed the action
    performed_by_email = models.EmailField()

    # Date tracking
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscriptions_history'
        ordering = ['-created_at']
        verbose_name_plural = 'Subscription histories'

    def __str__(self):
        return f"{self.organization.name} - {self.action} - {self.created_at}"
