import os
from .models import Organization, Domain
from rest_framework.response import Response
from django.db import transaction, connection
from django_tenants.utils import schema_context
from ..subscriptions.models import SubscriptionPlan
from utils.registration_mail import send_verification_email
from .serializers import OrganizationRegisterSerializer
from rest_framework import status, permissions, generics
from ..subscriptions.services import SubscriptionService


class OrganizationRegisterView(generics.CreateAPIView):
    """
    Register a new organization (tenant) with subscription plan.

    Flow:
    1. User selects a plan and registers
    2. Create organization (tenant + schema)
    3. Create domain for routing
    4. Create admin user in tenant schema
    5. Assign subscription plan (paid)

    Available to anyone for self-service registration.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationRegisterSerializer

    def post(self, request):
        # Ensure we're in public schema
        if connection.schema_name != 'public':
            return Response(
                {"error": "Registration only allowed from public domain."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate input
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # try:
        #     # Atomic so either all of the below queries execute or none
        #     with transaction.atomic():
        #         # Get or use default subscription plan
        #         plan = self._get_subscription_plan(serializer.validated_data)

        #         # Create organization (tenant)
        #         organization = self._create_organization(
        #             serializer.validated_data
        #         )

        #         # Create domain
        #         domain = self._create_domain(organization)

        #         # Create admin user in tenant schema
        #         admin_user, generated_password = self._create_admin_user(
        #             organization,
        #             serializer.validated_data
        #         )

        #         # Assign subscription plan
        #         subscription_info = self._assign_subscription_plan(
        #             organization,
        #             plan,
        #             serializer.validated_data['email']
        #         )

        #         send_verification_email(admin_user, generated_password)

        try:
            plan = self._get_subscription_plan()

            # Outside atomic — django-tenants needs its own transaction control
            organization = self._create_organization(serializer.validated_data)
            domain = self._create_domain(organization)

            # Now wrap only the remaining operations
            with transaction.atomic():
                admin_user, generated_password = self._create_admin_user(
                    organization, serializer.validated_data
                )
                subscription_info = self._assign_subscription_plan(
                    organization, plan, serializer.validated_data['email']
                )

            send_verification_email(admin_user, generated_password)
            return Response(
                {
                    'success': True,
                    'message': 'Organization created successfully. '
                    'Please check your registered mail for verification',
                    'data': {
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
                        },
                        'subscription': subscription_info
                    }
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            if 'organization' in locals():
                organization.delete()
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

    def _get_subscription_plan(self):
        """Get subscription plan from request plan"""
        try:
            return SubscriptionPlan.objects.get(
                slug='trial',
                is_active=True,
                is_public=True
            )
        except SubscriptionPlan.DoesNotExist:
            # Fallback to first free plan
            plan = SubscriptionPlan.objects.filter(
                price=0,
                is_active=True,
                is_public=True
            ).first()

            if not plan:
                raise Exception(
                    "No default trial plan found. "
                    "Please create a plan with slug 'trial' or a free plan."
                )
            return plan

    def _create_organization(self, validated_data):
        """
        Create the organization (tenant)
        """
        return Organization.objects.create(
            name=validated_data['organization_name'],
            schema_name=validated_data['organization_schema_name'],
            contact_email=validated_data['contact_email'],
            contact_phone=validated_data.get('contact_phone', ''),
        )

    def _create_domain(self, organization):
        """
        Create domain for tenant routing
        """
        primary_domain_name = os.getenv('DOMAIN')

        if not primary_domain_name:
            raise Exception(
                'DOMAIN environment variable not set. '
                'Please add DOMAIN to your .env file.'
            )

        return Domain.objects.create(
            domain=f"{organization.schema_name}.{primary_domain_name}",
            tenant=organization,
            is_primary=True,
        )

    def _create_admin_user(self, organization, validated_data):
        """Create admin user and generate password in correct schema"""
        with schema_context(organization.schema_name):
            from apps.users.models import User

            # Create user
            admin_user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                is_superuser=validated_data.get('is_superuser', False),
                is_tenant_admin=validated_data.get('is_tenant_admin', True),
                is_staff=validated_data.get('is_staff', False),
            )
            # Generate password WHILE STILL in schema context
            generated_password = admin_user.generate_password()

            # Store password for email (return as tuple)
            return admin_user, generated_password

    def _assign_subscription_plan(self, organization, plan, user_email):
        """
        Assign subscription plan to organization
        """
        # Activate paid plan immediately
        # Note: In future verify payment first
        SubscriptionService.subscribe(
            organization=organization,
            plan=plan,
            performed_by_email=user_email
        )

        return {
            'plan': {
                'id': plan.id,
                'name': plan.name,
                'price': str(plan.price),
            },
            'status': 'active',
            'subscription_end_date': organization.subscription_end_date.isoformat(),
            'message': f'Subscription activated for {plan.name}'
        }
