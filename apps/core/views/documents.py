from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.http import Http404
from django.db import connection
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema

from apps.core.models.documents import Document
from apps.core.serializers.documents import (
    DocumentUploadSerializer,
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentUpdateSerializer
)
from apps.core.services.documents import DocumentService
from apps.permissions import require_permissions


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Document CRUD operations

    Endpoints:
    - POST   /api/documents/                              - Upload a new document
    - GET    /api/documents/                              - List all documents
    - GET    /api/documents/{id}/                         - Get document details
    - PATCH  /api/documents/{id}/                         - Update document metadata
    - DELETE /api/documents/{id}/                         - Soft delete record + delete file from R2
    - GET    /api/documents/{id}/download/                - Get signed R2 download URL
    - GET    /api/documents/patient/{patient_id}/         - List documents for a patient
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

    @require_permissions('documents.read')
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @require_permissions('documents.read')
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @require_permissions('documents.update')
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Upload a patient document",
        responses={201: DocumentUploadSerializer()},
        consumes=['multipart/form-data']
    )
    @require_permissions('documents.create')
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

        schema_name = connection.schema_name
        from apps.core.tasks import process_document_task
        process_document_task.delay(document.id, schema_name)

        return Response(
            DocumentDetailSerializer(
                document, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @require_permissions('documents.delete')
    def destroy(self, request, *args, **kwargs):
        """
        Delete a document — soft deletes the DB record and hard deletes the file from R2
        """
        document = self.get_object()
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
    @require_permissions('documents.read')
    def download(self, request, pk=None):
        """
        Returns a signed R2 URL for direct file download.
        The client uses this URL to download the file directly from R2.
        URL expires after the time set in AWS_QUERYSTRING_EXPIRE (default 1 hour).
        """
        document = self.get_object()

        if document.status != 'completed':
            return Response(
                {'error': 'Document is still being processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        signed_url = document.get_signed_url()
        if not signed_url:
            raise Http404("Document file not found")

        return Response({
            'download_url': signed_url,
            'expires_in': getattr(settings, 'AWS_QUERYSTRING_EXPIRE', 3600)
        })

    @action(detail=False, methods=['get'], url_path='patient/(?P<patient_id>[^/.]+)')
    @require_permissions('documents.read')
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
