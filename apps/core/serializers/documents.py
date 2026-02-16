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
        """Validate the uploaded file"""
        is_valid, error = DocumentService.validate_file(file)
        if not is_valid:
            raise serializers.ValidationError(error)
        return file

    def validate_patient(self, patient):
        """Validate patient exists and is active"""
        if not patient.is_active:
            raise serializers.ValidationError(
                "Cannot upload documents for inactive patients")
        return patient

    def create(self, validated_data):
        """Create document with file handling"""
        file = validated_data.pop('file')
        patient = validated_data.get('patient')
        title = validated_data.get('title', file.name)
        description = validated_data.get('description', '')
        document_type = validated_data.get('document_type', 'other')

        # Get user from context
        user = self.context['request'].user

        # Save document using service
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
        """Get the name of the user who uploaded the document"""
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.username
        return None

    def get_file_size_mb(self, obj):
        """Convert file size to MB"""
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
        """Get the name of the user who uploaded the document"""
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.username
        return None

    def get_file_size_mb(self, obj):
        """Convert file size to MB"""
        return round(obj.file_size / (1024 * 1024), 2)

    def get_file_url(self, obj):
        """Get file download URL"""
        request = self.context.get('request')
        if obj.file and request:
            # Return relative URL - the view will handle actual file serving
            return request.build_absolute_uri(f'/api/documents/{obj.id}/download/')
        return None


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
        """Update only allowed fields"""
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get(
            'description', instance.description)
        instance.document_type = validated_data.get(
            'document_type', instance.document_type)
        instance.save()
        return instance
