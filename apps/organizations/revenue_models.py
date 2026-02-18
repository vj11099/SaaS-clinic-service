from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Revenue(models.Model):
    """
    Revenue model - PUBLIC schema
    Tracks all payments and revenue from subscriptions
    """
    TRANSACTION_TYPE_CHOICES = [
        ('subscription', 'Subscription Payment'),
        ('renewal', 'Renewal Payment'),
        ('upgrade', 'Upgrade Payment'),
        # ('refund', 'Refund'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='revenue_records'
    )
    plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT,
        related_name='revenue_records'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default='subscription'
    )

    # Reference to subscription history
    subscription_history = models.ForeignKey(
        'subscriptions.SubscriptionHistory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revenue_record'
    )

    # Additional info
    billing_interval = models.CharField(max_length=20)
    processed_by_email = models.EmailField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'revenue'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['transaction_type']),
        ]

    def __str__(self):
        return f"{self.organization.name} - ${self.amount} - {self.transaction_type}"
