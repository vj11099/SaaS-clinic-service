"""
Authentication views for PUBLIC SCHEMA.
Handles organization registration and super admin login.
"""
from rest_framework import status
from rest_framework.response import Response
from django.db import transaction, connection
from rest_framework import permissions, generics
from django_tenants.utils import schema_context
import os
from ..organizations.models import Organization, Domain
from ..organizations.serializers import OrganizationRegisterSerializer
from utils.exceptions import success_response


class OrganizationRegisterView(generics.CreateAPIView):
    """
    Register a new organization (tenant) and create an admin user.
    This endpoint is only available in the public schema.
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = OrganizationRegisterSerializer

    def post(self, request):
        serializer = OrganizationRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if connection.schema_name != 'public':
            return Response(
                {"error": "Registration only allowed from public domain."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            with transaction.atomic():
                # Create the organization (tenant)
                organization = Organization.objects.create(
                    name=serializer.validated_data['organization_name'],
                    schema_name=serializer.validated_data[
                        'organization_schema_name'
                    ],
                    contact_email=serializer.validated_data['contact_email'],
                    contact_phone=serializer.validated_data.get(
                        'contact_phone', ''
                    ),
                )

                domain_name = os.getenv('DOMAIN')
                if not domain_name:
                    raise Exception(
                        'Domain name not found, please update your .env'
                    )

                # Create the domain
                domain = Domain.objects.create(
                    # Change in production
                    domain=f"{organization.schema_name}.{domain_name}",
                    tenant=organization,
                    is_primary=True,
                )

                # Create admin user in the tenant's schema
                with schema_context(organization.schema_name):
                    from apps.users.models import User

                    admin_user = User.objects.create_user(
                        username=serializer.validated_data['username'],
                        email=serializer.validated_data['email'],
                        password=serializer.validated_data['password'],
                        first_name=serializer.validated_data.get(
                            'first_name', ''),
                        last_name=serializer.validated_data.get(
                            'last_name', ''),
                        is_tenant_admin=True,
                        is_staff=True,
                    )

                return success_response(
                    data={
                        'organization': {
                            'id': organization.id,
                            'name': organization.name,
                            'schema_name': organization.schema_name,
                        },
                        'domain': domain.domain,
                        'admin_user': {
                            'id': admin_user.id,
                            'username': admin_user.username,
                            'email': admin_user.email,
                        }
                    },
                    message='Organization created successfully',
                    status=status.HTTP_201_CREATED
                )

        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': {
                        'message': 'Failed to create organization',
                        'details': str(e)
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
