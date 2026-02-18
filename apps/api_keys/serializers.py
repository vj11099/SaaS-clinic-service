from rest_framework import serializers
from .models import APIKey
from .utils import APIKeyEncryption


class APIKeyListSerializer(serializers.ModelSerializer):
    """Serializer for listing API keys - shows masked values only"""

    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    # api_key_preview = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = [
            'id',
            'service_name',
            # 'api_key_preview',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return f"{obj.updated_by.first_name} {obj.updated_by.last_name}".strip() or obj.updated_by.username
        return None

    # def get_api_key_preview(self, obj):
    #     """Show masked preview of the key"""
    #     try:
    #         decrypted = APIKeyEncryption.decrypt(obj.encrypted_api_key)
    #         if len(decrypted) > 8:
    #             return f"{decrypted[:4]}...{decrypted[-4:]}"
    #         return "****"
    #     except Exception:
    #         return "[ENCRYPTED]"


class APIKeyDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving a single API key - shows decrypted value"""

    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    api_key = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = [
            'id',
            'service_name',
            'api_key',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return f"{obj.updated_by.first_name} {obj.updated_by.last_name}".strip() or obj.updated_by.username
        return None

    def get_api_key(self, obj):
        """Return decrypted API key value"""
        try:
            return APIKeyEncryption.decrypt(obj.encrypted_api_key)
        except Exception as e:
            return f"[DECRYPTION_ERROR: {str(e)}]"


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new API key"""

    api_key = serializers.CharField(
        write_only=True,
        help_text="API key value (will be encrypted before storage)"
    )

    class Meta:
        model = APIKey
        fields = [
            'service_name',
            'api_key',
            'is_active',
        ]

    def validate_service_name(self, value):
        """Ensure service name is lowercase and doesn't already exist"""
        value = value.lower().strip()
        if APIKey.objects.filter(service_name=value).exists():
            raise serializers.ValidationError(
                f"API key for service '{
                    value}' already exists. Use PUT/PATCH to update."
            )
        return value

    def validate_api_key(self, value):
        """Validate API key is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("API key cannot be empty")
        return value.strip()

    def create(self, validated_data):
        api_key_plain = validated_data.pop('api_key')
        user = self.context['request'].user

        # Encrypt the key
        try:
            encrypted_key = APIKeyEncryption.encrypt(api_key_plain)
        except Exception as e:
            raise serializers.ValidationError(f"Encryption failed: {str(e)}")

        # Create the record
        api_key_obj = APIKey.objects.create(
            service_name=validated_data['service_name'],
            encrypted_api_key=encrypted_key,
            is_active=validated_data.get('is_active', True),
            created_by=user,
            updated_by=user
        )

        return api_key_obj


class APIKeyUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an existing API key"""

    api_key = serializers.CharField(
        write_only=True,
        required=False,
        help_text="New API key value (will be encrypted before storage)"
    )

    class Meta:
        model = APIKey
        fields = [
            'api_key',
            'is_active',
        ]

    def validate_api_key(self, value):
        """Validate API key is not empty if provided"""
        if value is not None and not value.strip():
            raise serializers.ValidationError("API key cannot be empty")
        return value.strip() if value else None

    def update(self, instance, validated_data):
        user = self.context['request'].user
        api_key_plain = validated_data.pop('api_key', None)

        # Update API key if provided
        if api_key_plain:
            try:
                instance.encrypted_api_key = APIKeyEncryption.encrypt(
                    api_key_plain)
            except Exception as e:
                raise serializers.ValidationError(
                    f"Encryption failed: {str(e)}")

        # Update is_active if provided
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']

        instance.updated_by = user
        instance.save()

        return instance
