from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class RequestLog(models.Model):
    """
    Tenant-specific request logging model
    Stores detailed information about each API request
    Stored in each tenant's schema automatically
    """
    # Request metadata
    method = models.CharField(max_length=10, db_index=True)
    path = models.CharField(max_length=500, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Request data
    headers = models.JSONField(default=dict, blank=True)
    query_params = models.JSONField(default=dict, blank=True)
    body = models.JSONField(default=dict, blank=True, null=True)

    # User information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_logs'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Response data
    status_code = models.IntegerField(db_index=True)
    response_time_ms = models.FloatField(
        help_text="Response time in milliseconds")
    response_body = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Only stored for failed requests (status >= 400)"
    )

    # Indexing for failed requests
    is_failed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if status_code >= 400"
    )

    class Meta:
        db_table = 'request_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['method', 'path']),
            models.Index(fields=['is_failed', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['status_code']),
        ]
        verbose_name = 'Request Log'
        verbose_name_plural = 'Request Logs'

    def __str__(self):
        return f"{self.method} {self.path} - {self.status_code}"

    @property
    def is_success(self):
        """Check if request was successful"""
        return self.status_code < 400
