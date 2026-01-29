from ..models.patients import Patient
from rest_framework import serializers


class PatientSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    date_of_birth = serializers.CharField()
    gender = serializers.CharField()
    medical_record_number = serializers.CharField()
    allergies = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'first_name', 'last_name', 'date_of_birth',
            'gender', 'medical_record_number', 'allergies',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        patient = Patient()
        patient.first_name = validated_data['first_name']
        patient.last_name = validated_data['last_name']
        patient.date_of_birth = validated_data['date_of_birth']
        patient.gender = validated_data['gender']
        patient.medical_record_number = validated_data['medical_record_number']
        patient.allergies = validated_data.get('allergies')
        patient.save()
        return patient

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get(
            'first_name', instance.first_name)
        instance.last_name = validated_data.get(
            'last_name', instance.last_name)
        instance.date_of_birth = validated_data.get(
            'date_of_birth', instance.date_of_birth)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.medical_record_number = validated_data.get(
            'medical_record_number', instance.medical_record_number)
        instance.allergies = validated_data.get(
            'allergies', instance.allergies)
        instance.save()
        return instance
