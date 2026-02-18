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
    - Validate file exists in R2 and is a valid PDF
    - Verify file size matches metadata
    - Mark as completed or failed

    Args:
        document_id: ID of the document to process
        schema_name: Tenant schema name (REQUIRED for multi-tenant setup)
    """
    if not schema_name:
        error_msg = f"Schema name not provided for document {
            document_id}. Cannot process without tenant context."
        logger.error(error_msg)
        return {'success': False, 'error': error_msg, 'document_id': document_id}

    logger.info(f"[TASK START] Document ID: {
                document_id}, Schema: {schema_name}")

    try:
        with schema_context(schema_name):
            # Verify we're in the correct schema
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema()")
                current_schema = cursor.fetchone()[0]
                logger.info(f"[SCHEMA CHECK] Current: {
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
            document.status = 'processing'
            document.save(update_fields=['status', 'updated_at'])
            logger.info(f"[STATUS UPDATE] Document {
                        document_id} marked as processing")

            # Perform processing
            try:
                if not document.file:
                    raise Exception("Document file field is empty")

                # 1. Validate file exists in R2 and is a valid PDF
                # Opens the file directly from R2 storage to read header bytes
                try:
                    with document.file.open('rb') as f:
                        header = f.read(4)
                except Exception as e:
                    raise Exception(
                        f"Could not open file from R2 storage: {str(e)}")

                if header != b'%PDF':
                    raise Exception(
                        "File does not appear to be a valid PDF (invalid header)")

                logger.info(
                    f"[FILE VALID] PDF header confirmed for document {document_id}")

                # 2. Verify file size matches metadata
                actual_size = document.file.size
                if actual_size != document.file_size:
                    logger.warning(f"[SIZE MISMATCH] Expected: {
                                   document.file_size}, Actual: {actual_size}")
                    document.file_size = actual_size
                    document.save(update_fields=['file_size', 'updated_at'])

                logger.info(f"[FILE SIZE] {actual_size} bytes")

                # 3. Additional processing can be added here
                # - Extract text content
                # - Generate thumbnails
                # - OCR if needed

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

                DocumentService.mark_processing_complete(
                    document, success=False, error=error_msg)

                # Exponential backoff retry: 60s, 120s, 240s
                retry_countdown = 60 * (2 ** self.request.retries)
                logger.info(f"[RETRY] Attempt {
                            self.request.retries + 1}/{self.max_retries}, waiting {retry_countdown}s")
                raise self.retry(exc=e, countdown=retry_countdown)

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
    Periodic task to clean up orphaned files in R2
    (files that exist in R2 but have no corresponding DB record)

    TODO: Implementation requires listing R2 bucket objects and
    cross-referencing with the database across all tenant schemas.
    Use boto3 S3 client with paginator to list objects:

        s3 = boto3.client('s3', ...)
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME):
            for obj in page.get('Contents', []):
                # parse schema + patient_id from obj['Key']
                # check if document exists in that tenant schema
                # delete from R2 if no DB record found

    Should be run periodically via celery beat.
    """
    logger.info("Orphaned files cleanup not yet implemented for R2 storage")


@shared_task
def cleanup_deleted_documents():
    """
    Periodic task to permanently remove soft-deleted documents older than 30 days.
    Deletes the file from R2 then removes the DB record.

    Should be run periodically via celery beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django_tenants.utils import get_tenant_model

    logger.info("Starting deleted documents cleanup")

    try:
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.filter(is_active=True)

        retention_days = 30
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        total_cleaned = 0

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                from apps.core.models.documents import Document

                old_deleted = Document.all_objects.filter(
                    is_deleted=True,
                    deleted_at__lt=cutoff_date
                )

                count = old_deleted.count()
                if count == 0:
                    continue

                logger.info(f"Cleaning {count} old deleted documents in schema {
                            tenant.schema_name}")

                # Delete file from R2 before removing DB record
                for document in old_deleted:
                    if document.file:
                        try:
                            document.file.delete(save=False)
                        except Exception as e:
                            logger.warning(
                                f"Could not delete R2 file for document {
                                    document.id}: {str(e)}"
                            )

                old_deleted.delete()
                total_cleaned += count

        logger.info(f"Deleted documents cleanup completed. Total cleaned: {
                    total_cleaned}")

    except Exception as e:
        logger.error(f"Error during deleted documents cleanup: {
                     str(e)}", exc_info=True)
        raise
