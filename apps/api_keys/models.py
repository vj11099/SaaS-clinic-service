from django.db import models
from django.conf import settings


class APIKey(models.Model):
    """
    Store encrypted third-party API keys in public schema.
    Keys are encrypted using Fernet symmetric encryption.
    """

    service_name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Service identifier (e.g., 'openai', 'stripe', 'twilio')"
    )
    encrypted_api_key = models.TextField(
        help_text="Fernet-encrypted API key value"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this key is currently active"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_api_keys',
        help_text="User who created this key"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_api_keys',
        help_text="User who last updated this key"
    )

    class Meta:
        db_table = 'api_keys'
        ordering = ['service_name']
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.service_name} ({status})"
