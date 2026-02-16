from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings
# import os


class DocumentQuerySet(models.QuerySet):
    """Custom QuerySet for Document filtering"""

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class DocumentManager(models.Manager):
    """Manager for Document model"""

    def get_queryset(self):
        return DocumentQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        return DocumentQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def deleted(self):
        return self.all_with_deleted().deleted()


class Document(models.Model):
    """
    Document model - TENANT schema
    Stores PDF documents associated with patients
    """

    DOCUMENT_TYPE_CHOICES = [
        ('medical_record', 'Medical Record'),
        ('lab_report', 'Lab Report'),
        ('prescription', 'Prescription'),
        ('insurance', 'Insurance Document'),
        ('other', 'Other'),
    ]

    # Relations
    patient = models.ForeignKey(
        'core.Patient',
        on_delete=models.CASCADE,
        related_name='documents'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )

    # Document metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        default='other'
    )

    # File information
    file = models.FileField(
        upload_to='documents/',  # Will be overridden in service
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # Size in bytes
    mime_type = models.CharField(max_length=100, default='application/pdf')

    # Processing status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    processing_error = models.TextField(blank=True, null=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deleted_documents'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DocumentManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'is_deleted']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self):
        return f"{self.title} - {self.patient}"

    def get_file_path(self):
        """Get the full file path"""
        if self.file:
            return self.file.path
        return None

    def get_file_url(self):
        """Get the file URL"""
        if self.file:
            return self.file.url
        return None
