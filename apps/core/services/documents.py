import os
import mimetypes
from django.conf import settings
# from django.core.files.base import ContentFile
from django.db import connection, models
from django.utils import timezone
from pathlib import Path


class DocumentService:
    """
    Service class for handling document operations
    Handles file storage, validation, and cleanup
    """

    @staticmethod
    def get_upload_path(patient_id, filename):
        """
        Generate upload path for document
        Format: documents/{schema_name}/{patient_id}/{filename}
        """
        schema_name = connection.schema_name
        return os.path.join('documents', schema_name, str(patient_id), filename)

    @staticmethod
    def validate_file(file):
        """
        Validate uploaded file
        Returns (is_valid, error_message)
        """
        # Check file size
        max_size = getattr(settings, 'MAX_DOCUMENT_SIZE', 5 * 1024 * 1024)
        if file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds maximum allowed size of {max_size_mb}MB"

        # Check MIME type
        mime_type = mimetypes.guess_type(file.name)[0]
        allowed_types = getattr(
            settings, 'ALLOWED_DOCUMENT_TYPES', ['application/pdf'])

        if mime_type not in allowed_types:
            return False, "Invalid file type. Only PDF files are allowed."

        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext != '.pdf':
            return False, "Invalid file extension. Only .pdf files are allowed."

        return True, None

    @staticmethod
    def save_document(
        file,
        patient,
        uploaded_by,
        title=None,
        description=None,
        document_type='other'
    ):
        """
        Save document with validation
        Returns (document, error_message)
        """
        from apps.core.models.documents import Document

        # Validate file
        is_valid, error = DocumentService.validate_file(file)
        if not is_valid:
            return None, error

        try:
            # Generate unique filename
            original_filename = file.name
            file_path = DocumentService.get_upload_path(
                patient.id, original_filename)

            # Create document instance
            document = Document(
                patient=patient,
                uploaded_by=uploaded_by,
                title=title or original_filename,
                description=description,
                document_type=document_type,
                file_name=original_filename,
                file_size=file.size,
                mime_type=mimetypes.guess_type(
                    file.name)[0] or 'application/pdf',
                status='pending'
            )

            # Save file
            document.file.save(file_path, file, save=False)
            document.save()

            return document, None

        except Exception as e:
            return None, f"Error saving document: {str(e)}"

    @staticmethod
    def delete_document(document, deleted_by):
        """
        Soft delete document from DB and hard delete file from storage
        """
        try:
            # Get file path before marking as deleted
            file_path = document.get_file_path()

            # Soft delete in database
            document.is_deleted = True
            document.deleted_at = timezone.now()
            document.deleted_by = deleted_by
            document.save(
                update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

            # Hard delete file from storage
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

                # Try to remove empty directories
                DocumentService._cleanup_empty_directories(file_path)

            return True, None

        except Exception as e:
            return False, f"Error deleting document: {str(e)}"

    @staticmethod
    def _cleanup_empty_directories(file_path):
        """
        Remove empty parent directories after file deletion
        Stops at MEDIA_ROOT
        """
        try:
            media_root = Path(settings.MEDIA_ROOT)
            current_dir = Path(file_path).parent

            # Walk up the directory tree
            while current_dir != media_root and current_dir.exists():
                # Check if directory is empty
                if not any(current_dir.iterdir()):
                    current_dir.rmdir()
                    current_dir = current_dir.parent
                else:
                    break
        except Exception:
            # Silently ignore cleanup errors
            pass

    # @staticmethod
    # def get_document_stats(patient):
    #     """
    #     Get document statistics for a patient
    #     """
    #     from apps.core.models.documents import Document

    #     documents = Document.objects.filter(patient=patient)

    #     return {
    #         'total_documents': documents.count(),
    #         'total_size_bytes': documents.aggregate(
    #             total=models.Sum('file_size')
    #         )['total'] or 0,
    #         'by_type': documents.values('document_type').annotate(
    #             count=models.Count('id')
    #         ),
    #         'by_status': documents.values('status').annotate(
    #             count=models.Count('id')
    #         )
    #     }

    @staticmethod
    def mark_processing_complete(document, success=True, error=None):
        """
        Mark document processing as complete or failed
        """
        if success:
            document.status = 'completed'
            document.processing_error = None
        else:
            document.status = 'failed'
            document.processing_error = error

        document.save(
            update_fields=['status', 'processing_error', 'updated_at'])
        return document
