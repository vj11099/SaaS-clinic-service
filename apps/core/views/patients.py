from rest_framework.permissions import DjangoModelPermissions
from ..models.patients import Patient, crypto
from ..serializers.patients import PatientSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import status
from rest_framework.response import Response
from rest_framework import viewsets


class PatientViews(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter]

    def get_queryset(self):
        queryset = Patient.objects.all()
        mrn = self.request.query_params.get('medical_record_number', None)
        if mrn:
            mrn_hash = crypto.hash(mrn)
            queryset = queryset.filter(hashed_medical_record_number=mrn_hash)

        first_name = self.request.query_params.get('first_name', None)
        last_name = self.request.query_params.get('last_name', None)

        if first_name or last_name:
            patients = list(queryset)
            filtered_patients = []
            for patient in patients:
                match = True
                if first_name.lower() not in patient.first_name.lower():
                    match = False
                if last_name.lower() not in patient.last_name.lower():
                    match = False
                if match:
                    filtered_patients.append(patient.id)

            queryset = queryset.filter(id__in=filtered_patients)

        return queryset

    def create(self, request):
        serializer = PatientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(
            instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def destroy(self, instance, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_active = False
            instance.save()

            return Response(
                data="deleted successfully",
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'{e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                exception=True
            )
