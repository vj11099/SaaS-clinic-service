from django.db import models
from django.core.validators import MinValueValidator


class SubscriptionPlan(models.Model):
    """
    PUBLIC
    Available to all tenants for selection
    """
    BILLING_INTERVAL_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('lifetime', 'Lifetime'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

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
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object with feature flags and limits"
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this plan is publicly available for subscription"
    )
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions_plan'
        ordering = ['sort_order', 'price']

    def __str__(self):
        return f"{self.name} ({self.get_billing_interval_display()})"

    def get_duration_days(self):
        """Get duration in days based on billing interval"""
        if self.billing_interval == 'monthly':
            return 30
        elif self.billing_interval == 'yearly':
            return 365
        elif self.billing_interval == 'lifetime':
            return 36500  # 100 years
        return 30


class SubscriptionHistory(models.Model):
    """
    PUBLIC
    Tracks all subscription changes for a tenant
    """
    ACTION_CHOICES = [
        ('subscribed', 'Subscribed'),
        ('renewed', 'Renewed'),
        ('upgraded', 'Upgraded'),
        ('downgraded', 'Downgraded'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('trial_started', 'Trial Started'),
        ('trial_ended', 'Trial Ended'),
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
