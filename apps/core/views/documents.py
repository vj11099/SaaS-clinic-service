from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.http import FileResponse, Http404
from django.db import connection
from drf_yasg.utils import swagger_auto_schema

from apps.core.models.documents import Document
from apps.core.serializers.documents import (
    DocumentUploadSerializer,
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentUpdateSerializer
)
from apps.core.services.documents import DocumentService


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Document CRUD operations

    Endpoints:
    - POST /api/documents/ - Upload a new document
    - GET /api/documents/ - List all documents
    - GET /api/documents/{id}/ - Get document details
    - PATCH /api/documents/{id}/ - Update document metadata
    - DELETE /api/documents/{id}/ - Delete document (soft delete + hard delete file)
    - GET /api/documents/{id}/download/ - Download document file
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['patient', 'document_type', 'status', 'uploaded_by']
    search_fields = ['title', 'description', 'file_name']
    ordering_fields = ['created_at', 'updated_at', 'file_size', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        return Document.objects.all().select_related('patient', 'uploaded_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentUploadSerializer
        elif self.action in ['update', 'partial_update']:
            return DocumentUpdateSerializer
        elif self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentListSerializer

    @swagger_auto_schema(
        operation_description="Upload a patient document",
        responses={201: DocumentUploadSerializer()},
        consumes=['multipart/form-data']
    )
    def create(self, request, *args, **kwargs):
        """
        Upload a new document

        Request body:
        - file: PDF file (required, max 5MB)
        - patient: Patient ID (required)
        - title: Document title (optional, defaults to filename)
        - description: Document description (optional)
        - document_type: Type of document (optional, defaults to 'other')
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # Get current schema name from connection
        schema_name = connection.schema_name

        # Trigger async processing task with schema name
        from apps.core.tasks import process_document_task
        process_document_task.delay(
            document.id, schema_name)  # ✓ Pass schema_name!

        return Response(
            DocumentDetailSerializer(
                document, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        """
        Delete a document (soft delete from DB, hard delete file from storage)
        """
        document = self.get_object()

        # Delete using service
        success, error = DocumentService.delete_document(
            document, request.user)

        if not success:
            return Response(
                {'error': error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'message': 'Document deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """
        Download document file

        Returns the PDF file with appropriate headers
        """
        document = self.get_object()

        if document.status != 'completed':
            return Response(
                {'error': 'Document is still being processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        file_path = document.get_file_path()

        if not file_path or not document.file:
            raise Http404("Document file not found")

        # Serve file
        try:
            response = FileResponse(
                document.file.open('rb'),
                content_type=document.mime_type
            )
            response['Content-Disposition'] = f'attachment; filename="{
                document.file_name}"'
            response['Content-Length'] = document.file_size
            return response
        except Exception as e:
            return Response(
                {'error': f'Error downloading file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='patient/(?P<patient_id>[^/.]+)')
    def patient_documents(self, request, patient_id=None):
        """
        Get all documents for a specific patient

        GET /api/documents/patient/{patient_id}/
        """
        queryset = self.filter_queryset(
            self.get_queryset().filter(patient_id=patient_id)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='debug')
    def debug_status(self, request, pk=None):
        """
        Debug endpoint to check document status and file info
        """
        document = self.get_object()

        import os
        file_path = document.get_file_path()
        file_exists = os.path.exists(file_path) if file_path else False

        return Response({
            'id': document.id,
            'title': document.title,
            'status': document.status,
            'processing_error': document.processing_error,
            'file_field': str(document.file),
            'file_path': file_path,
            'file_exists': file_exists,
            'file_size': document.file_size,
            'mime_type': document.mime_type,
            'schema': connection.schema_name,
            'created_at': document.created_at,
            'updated_at': document.updated_at,
        })

    @action(detail=True, methods=['post'], url_path='reprocess')
    def reprocess(self, request, pk=None):
        """
        Manually trigger reprocessing of a document
        """
        document = self.get_object()

        # Reset status to pending
        document.status = 'pending'
        document.processing_error = None
        document.save(
            update_fields=['status', 'processing_error', 'updated_at'])

        # Get current schema and trigger task
        schema_name = connection.schema_name
        from apps.core.tasks import process_document_task
        process_document_task.delay(document.id, schema_name)

        return Response({
            'message': 'Document reprocessing triggered',
            'document_id': document.id,
            'status': document.status
        })

    # @action(detail=False, methods=['get'], url_path='stats/patient/(?P<patient_id>[^/.]+)')
    # def patient_stats(self, request, patient_id=None):
    #     """
    #     Get document statistics for a specific patient

    #     GET /api/documents/stats/patient/{patient_id}/
    #     """
    #     from apps.core.models.patients import Patient

    #     patient = get_object_or_404(Patient, id=patient_id)
    #     stats = DocumentService.get_document_stats(patient)

    #     return Response(stats)
