import django_filters
from ..models.patients import Patient, crypto


class PatientFilter(django_filters.FilterSet):
    medical_record_number = django_filters.CharFilter(
        method='filter_medical_record_number'
    )
    first_name = django_filters.CharFilter(method='filter_first_name')
    last_name = django_filters.CharFilter(method='filter_last_name')

    class Meta:
        model = Patient
        fields = ['medical_record_number', 'first_name', 'last_name']

    def filter_medical_record_number(self, queryset, name, value):
        """Filter by hashed medical record number"""
        if value:
            hashed_value = crypto.hash(value)
            return queryset.filter(hashed_medical_record_number=hashed_value)
        return queryset

    def filter_first_name(self, queryset, name, value):
        """Filter by hashed first name"""
        if value:
            hashed_value = crypto.hash(value.lower())
            return queryset.filter(first_name_hash=hashed_value)
        return queryset

    def filter_last_name(self, queryset, name, value):
        """Filter by hashed last name"""
        if value:
            hashed_value = crypto.hash(value.lower())
            return queryset.filter(last_name_hash=hashed_value)
        return queryset
