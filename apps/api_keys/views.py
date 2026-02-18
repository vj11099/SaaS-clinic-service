from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import APIKey
from .serializers import (
    APIKeyListSerializer,
    APIKeyDetailSerializer,
    APIKeyCreateSerializer,
    APIKeyUpdateSerializer
)


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing encrypted API keys in public schema

    Endpoints:
    - GET    /api/api-keys/              - List all keys (masked)
    - POST   /api/api-keys/              - Create new key
    - GET    /api/api-keys/{id}/         - Get single key (decrypted)
    - PUT    /api/api-keys/{id}/         - Update key
    - PATCH  /api/api-keys/{id}/         - Partial update
    - DELETE /api/api-keys/{id}/         - Delete key
    - GET    /api/api-keys/by-service/{service_name}/ - Get key by service name
    """

    permission_classes = [IsAuthenticated]
    # TODO: Add your custom permission here, e.g.:
    # permission_classes = [IsAuthenticated, HasAPIKeyManagementPermission]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'service_name']
    search_fields = ['service_name']
    ordering_fields = ['service_name', 'created_at', 'updated_at']
    ordering = ['service_name']

    def get_queryset(self):
        return APIKey.objects.all().select_related('created_by', 'updated_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return APIKeyCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return APIKeyUpdateSerializer
        elif self.action == 'retrieve':
            return APIKeyDetailSerializer
        return APIKeyListSerializer

    @swagger_auto_schema(
        operation_description="Create a new encrypted API key",
        request_body=APIKeyCreateSerializer,
        responses={
            201: APIKeyDetailSerializer,
            400: "Validation error"
        }
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new API key

        The key value will be encrypted using Fernet before storage.
        Service name must be unique.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key = serializer.save()

        return Response(
            APIKeyDetailSerializer(api_key, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        operation_description="Get API key details with decrypted value",
        responses={
            200: APIKeyDetailSerializer,
            404: "API key not found"
        }
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single API key with decrypted value

        WARNING: This returns the actual API key in plain text.
        Ensure proper authentication and logging.
        """
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="List all API keys (values are masked)",
        responses={200: APIKeyListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        """
        List all API keys

        API key values are masked in the list view for security.
        Use the detail endpoint to see the full decrypted value.
        """
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete an API key permanently"""
        api_key = self.get_object()
        service_name = api_key.service_name
        api_key.is_active = False
        api_key.save()

        return Response(
            {'message': f"API key for '{service_name}' deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

    @swagger_auto_schema(
        method='get',
        operation_description="Get API key by service name (returns decrypted value)",
        manual_parameters=[
            openapi.Parameter(
                'service_name',
                openapi.IN_PATH,
                description="Service name (e.g., 'openai', 'stripe')",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: APIKeyDetailSerializer,
            404: "API key not found"
        }
    )
    @action(detail=False, methods=['get'], url_path='by-service/(?P<service_name>[^/.]+)')
    def by_service(self, request, service_name=None):
        """
        Get API key by service name

        Returns the decrypted API key for the specified service.
        """
        service_name = service_name.lower().strip()

        try:
            api_key = APIKey.objects.get(service_name=service_name)
        except APIKey.DoesNotExist:
            return Response(
                {'error': f"API key for service '{service_name}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = APIKeyDetailSerializer(
            api_key, context={'request': request})
        return Response(serializer.data)
