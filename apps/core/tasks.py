from celery import shared_task
from django.db import connection
from django_tenants.utils import schema_context
import logging

logger = logging.getLogger('celery')


@shared_task(bind=True, max_retries=3)
def process_document_task(self, document_id, schema_name=None):
    """
    Process uploaded document asynchronously

    Tasks performed:
    - Validate file integrity
    - Extract metadata
    - Mark as completed or failed

    Args:
        document_id: ID of the document to process
        schema_name: Tenant schema name (REQUIRED for multi-tenant setup)
    """
    # Validate schema_name was provided
    if not schema_name:
        error_msg = f"Schema name not provided for document {
            document_id}. Cannot process without tenant context."
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'document_id': document_id
        }

    logger.info(f"[TASK START] Document ID: {
                document_id}, Schema: {schema_name}")

    try:
        # Enter tenant schema context
        with schema_context(schema_name):
            # Verify we're in the correct schema
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema()")
                current_schema = cursor.fetchone()[0]
                logger.info(f"[SCHEMA CHECK] Current schema: {
                            current_schema}, Expected: {schema_name}")

                if current_schema != schema_name:
                    error_msg = f"Schema mismatch! Current: {
                        current_schema}, Expected: {schema_name}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}

            from apps.core.models.documents import Document
            from apps.core.services.documents import DocumentService

            # Get document
            try:
                document = Document.all_objects.get(id=document_id)
                logger.info(f"[DOCUMENT FOUND] ID: {document.id}, Title: {
                            document.title}, Status: {document.status}")
            except Document.DoesNotExist:
                error_msg = f"Document {
                    document_id} not found in schema {schema_name}"
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}

            # Mark as processing
            try:
                document.status = 'processing'
                document.save(update_fields=['status', 'updated_at'])
                logger.info(f"[STATUS UPDATE] Document {
                            document_id} marked as processing")
            except Exception as e:
                error_msg = f"Failed to update document status: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {'success': False, 'error': error_msg}

            # Perform processing tasks
            try:
                # 1. Validate file exists
                if not document.file:
                    raise Exception("Document file field is empty")

                logger.info(f"[FILE CHECK] Document file field: {
                            document.file}")

                file_path = document.get_file_path()
                logger.info(f"[FILE PATH] {file_path}")

                if not file_path:
                    raise Exception("Could not determine file path")

                # 2. Validate file integrity
                import os
                if not os.path.exists(file_path):
                    raise Exception(f"File does not exist at {file_path}")

                logger.info(f"[FILE EXISTS] File found at {file_path}")

                # 3. Verify file size matches metadata
                actual_size = os.path.getsize(file_path)
                if actual_size != document.file_size:
                    logger.warning(
                        f"[SIZE MISMATCH] Expected: {
                            document.file_size}, Actual: {actual_size}"
                    )
                    document.file_size = actual_size
                    document.save(update_fields=['file_size', 'updated_at'])

                logger.info(f"[FILE SIZE] {actual_size} bytes")

                # 4. Additional processing can be added here
                # - Extract text content
                # - Generate thumbnails
                # - OCR if needed
                # - etc.

                # Mark as completed
                DocumentService.mark_processing_complete(
                    document, success=True)
                logger.info(f"[SUCCESS] Document {
                            document_id} processed successfully in schema {schema_name}")

                return {
                    'success': True,
                    'document_id': document_id,
                    'schema': schema_name,
                    'status': 'completed'
                }

            except Exception as e:
                error_msg = str(e)
                logger.error(f"[PROCESSING ERROR] Document {
                             document_id}: {error_msg}", exc_info=True)

                # Mark as failed
                DocumentService.mark_processing_complete(
                    document,
                    success=False,
                    error=error_msg
                )

                # Retry if possible
                if self.request.retries < self.max_retries:
                    retry_countdown = 60 * (2 ** self.request.retries)
                    logger.info(f"[RETRY] Attempt {
                                self.request.retries + 1}/{self.max_retries}, waiting {retry_countdown}s")
                    raise self.retry(exc=e, countdown=retry_countdown)
                else:
                    logger.error(f"[MAX RETRIES] Document {document_id} failed after {
                                 self.max_retries} attempts")
                    return {
                        'success': False,
                        'error': error_msg,
                        'document_id': document_id,
                        'max_retries_reached': True
                    }

    except Exception as e:
        error_msg = f"Fatal error in document processing task: {str(e)}"
        logger.error(f"[FATAL ERROR] {error_msg}", exc_info=True)
        return {
            'success': False,
            'error': error_msg,
            'document_id': document_id,
            'schema': schema_name
        }


@shared_task
def cleanup_orphaned_files():
    """
    Periodic task to clean up orphaned files
    (files that exist in storage but not in database)

    Should be run periodically via celery beat
    """
    from django.conf import settings
    from pathlib import Path

    logger.info("Starting orphaned files cleanup")

    try:
        documents_path = Path(settings.MEDIA_ROOT) / 'documents'

        if not documents_path.exists():
            logger.info("Documents directory does not exist, skipping cleanup")
            return

        # TODO: Implement orphaned files cleanup logic
        # This is a placeholder for future implementation

        logger.info("Orphaned files cleanup completed")

    except Exception as e:
        logger.error(f"Error during orphaned files cleanup: {
                     str(e)}", exc_info=True)
        raise


@shared_task
def cleanup_deleted_documents():
    """
    Periodic task to permanently remove soft-deleted documents older than X days

    Should be run periodically via celery beat
    """
    from django.utils import timezone
    from datetime import timedelta
    from django_tenants.utils import get_tenant_model

    logger.info("Starting deleted documents cleanup")

    try:
        # Get all tenants
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.filter(is_active=True)

        retention_days = 30  # Keep soft-deleted documents for 30 days
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        total_cleaned = 0

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                from apps.core.models.documents import Document

                # Get documents deleted more than retention_days ago
                old_deleted = Document.all_objects.filter(
                    is_deleted=True,
                    deleted_at__lt=cutoff_date
                )

                count = old_deleted.count()
                if count > 0:
                    logger.info(
                        f"Cleaning {count} old deleted documents in schema {
                            tenant.schema_name}"
                    )

                    # Permanently delete from database
                    old_deleted.delete()
                    total_cleaned += count

        logger.info(f"Deleted documents cleanup completed. Total cleaned: {
                    total_cleaned}")

    except Exception as e:
        logger.error(f"Error during deleted documents cleanup: {
                     str(e)}", exc_info=True)
        raise
