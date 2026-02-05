from ..permissions import IsOrganizationMember
from ..models.patients import Patient
from ..serializers.patients import PatientSerializer
from ..services.patients import PatientFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import status
from rest_framework.response import Response
from rest_framework import viewsets
from django.db import IntegrityError


class PatientViews(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PatientFilter
    queryset = Patient.objects.all()

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {
                    "detail":
                    "A patient with this medical record number already exists."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_active = False
            instance.save()
            return Response(
                data={"detail": "deleted successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
