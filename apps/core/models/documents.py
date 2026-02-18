from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings


class DocumentQuerySet(models.QuerySet):
    """Custom QuerySet for Document filtering"""

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class DocumentManager(models.Manager):
    """Manager for Document model — excludes soft-deleted records by default"""

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
    Stores PDF documents associated with patients.
    Files are stored in Cloudflare R2 via django-storages S3 backend.
    """

    DOCUMENT_TYPE_CHOICES = [
        ('medical_record', 'Medical Record'),
        ('lab_report', 'Lab Report'),
        ('prescription', 'Prescription'),
        ('insurance', 'Insurance Document'),
        ('consent_form', 'Consent Form'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
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
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deleted_documents'
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
    # upload_to is overridden in DocumentService.save_document via file.save(file_path, ...)
    # actual path: documents/{schema_name}/{patient_id}/{filename}
    file = models.FileField(
        upload_to='documents/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # Size in bytes
    mime_type = models.CharField(max_length=100, default='application/pdf')

    # Processing status
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

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DocumentManager()       # excludes deleted by default
    all_objects = models.Manager()    # includes deleted — use carefully

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

    def get_signed_url(self):
        """
        Get a temporary signed R2 URL for file access.
        Expiry is controlled by AWS_QUERYSTRING_EXPIRE in settings (default 1 hour).
        """
        if self.file:
            return self.file.url
        return None
