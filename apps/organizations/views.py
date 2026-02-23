from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .serializers import OrganizationRegisterSerializer
from django.db import connection
from .tasks import register_organization_async
# views.py


class OrganizationRegisterView(generics.CreateAPIView):
    """
    Register a new organization (tenant) with subscription plan.

    Returns 202 immediately after validation.
    Everything else runs in a background Celery task:
      - Create org + domain
      - Send registration email
      - Create admin user
      - Assign subscription plan
      - Send verification email
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationRegisterSerializer

    def post(self, request):
        if connection.schema_name != 'public':
            return Response(
                {"error": "Registration only allowed from public domain."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # Sanitize before passing to Celery (must be JSON-serializable)
        validated_data = _serialize_validated_data(serializer.validated_data)

        # Fire and forget — return immediately
        register_organization_async.delay(validated_data)

        return Response(
            {
                'success': True,
                'message': (
                    'Registration received. Your organization is being set up. '
                    'You will receive a confirmation email shortly.'
                ),
                'data': {
                    'organization_name': validated_data['organization_name'],
                    'schema_name': validated_data['organization_schema_name'],
                    'contact_email': validated_data['contact_email'],
                    'username': validated_data['username'],
                }
            },
            status=status.HTTP_202_ACCEPTED
        )


def _serialize_validated_data(validated_data: dict) -> dict:
    """
    Celery serializes task args to JSON.
    Cast any non-primitive types so the task doesn't blow up on dispatch.
    """
    serialized = {}
    for key, value in validated_data.items():
        if hasattr(value, 'isoformat'):        # date / datetime
            serialized[key] = value.isoformat()
        elif hasattr(value, '__float__'):      # Decimal
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized
