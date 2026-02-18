from rest_framework import serializers
from apps.core.models.documents import Document
from apps.core.services.documents import DocumentService


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading documents"""

    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'patient',
            'title',
            'description',
            'document_type',
            'file',
        ]

    def validate_file(self, file):
        is_valid, error = DocumentService.validate_file(file)
        if not is_valid:
            raise serializers.ValidationError(error)
        return file

    def validate_patient(self, patient):
        if not patient.is_active:
            raise serializers.ValidationError(
                "Cannot upload documents for inactive patients")
        return patient

    def create(self, validated_data):
        file = validated_data.pop('file')
        patient = validated_data.get('patient')
        title = validated_data.get('title', file.name)
        description = validated_data.get('description', '')
        document_type = validated_data.get('document_type', 'other')
        user = self.context['request'].user

        document, error = DocumentService.save_document(
            file=file,
            patient=patient,
            uploaded_by=user,
            title=title,
            description=description,
            document_type=document_type
        )

        if error:
            raise serializers.ValidationError(error)

        return document


class DocumentListSerializer(serializers.ModelSerializer):
    """Serializer for listing documents"""

    uploaded_by_name = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'patient',
            'title',
            'description',
            'document_type',
            'file_name',
            'file_size',
            'file_size_mb',
            'mime_type',
            'status',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.username
        return None

    def get_file_size_mb(self, obj):
        if not obj.file_size:
            return 0
        return round(obj.file_size / (1024 * 1024), 2)


class DocumentDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed document view"""

    uploaded_by_name = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'patient',
            'title',
            'description',
            'document_type',
            'file_name',
            'file_size',
            'file_size_mb',
            'mime_type',
            'status',
            'processing_error',
            'uploaded_by',
            'uploaded_by_name',
            'file_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.username
        return None

    def get_file_size_mb(self, obj):
        if not obj.file_size:
            return 0
        return round(obj.file_size / (1024 * 1024), 2)

    def get_file_url(self, obj):
        """Get signed R2 URL for file download (expiry set in settings)"""
        return obj.get_signed_url()


class DocumentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating document metadata"""

    class Meta:
        model = Document
        fields = [
            'title',
            'description',
            'document_type',
        ]

    def update(self, instance, validated_data):
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get(
            'description', instance.description)
        instance.document_type = validated_data.get(
            'document_type', instance.document_type)
        instance.save()
        return instance
