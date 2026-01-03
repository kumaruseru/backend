"""
Common Core - Serializer Mixins.

Reusable serializer mixins and base classes.
"""
from rest_framework import serializers


class TimestampsMixin(serializers.Serializer):
    """Mixin that adds timestamp fields."""
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class SoftDeleteMixin(serializers.Serializer):
    """Mixin for soft delete fields."""
    is_deleted = serializers.BooleanField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True)


class DynamicFieldsSerializer(serializers.Serializer):
    """
    Serializer that allows specifying which fields to include.
    
    Usage:
        serializer = MySerializer(obj, fields=['id', 'name'])
        serializer = MySerializer(obj, exclude=['password'])
    """
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        exclude = kwargs.pop('exclude', None)
        
        super().__init__(*args, **kwargs)
        
        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)
        
        if exclude is not None:
            for field_name in exclude:
                self.fields.pop(field_name, None)


class WriteOnceFieldsMixin:
    """
    Mixin that makes specified fields read-only after creation.
    
    Usage:
        class MySerializer(WriteOnceFieldsMixin, serializers.ModelSerializer):
            class Meta:
                write_once_fields = ['email', 'username']
    """
    
    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        
        # Get write_once_fields from Meta
        write_once_fields = getattr(self.Meta, 'write_once_fields', [])
        
        # If updating (instance exists), make write_once fields read-only
        if self.instance is not None:
            for field_name in write_once_fields:
                kwargs = extra_kwargs.get(field_name, {})
                kwargs['read_only'] = True
                extra_kwargs[field_name] = kwargs
        
        return extra_kwargs


class NestedWriteSerializer(serializers.Serializer):
    """
    Base serializer for nested write operations.
    
    Override create_nested() and update_nested() for custom logic.
    """
    
    def create(self, validated_data):
        nested_data = self.extract_nested_data(validated_data)
        instance = super().create(validated_data)
        self.create_nested(instance, nested_data)
        return instance
    
    def update(self, instance, validated_data):
        nested_data = self.extract_nested_data(validated_data)
        instance = super().update(instance, validated_data)
        self.update_nested(instance, nested_data)
        return instance
    
    def extract_nested_data(self, validated_data) -> dict:
        """Extract nested data from validated_data."""
        return {}
    
    def create_nested(self, instance, nested_data):
        """Create nested objects after main instance is created."""
        pass
    
    def update_nested(self, instance, nested_data):
        """Update nested objects after main instance is updated."""
        pass


# ==================== Common Field Serializers ====================

class MoneyField(serializers.DecimalField):
    """Serializer field for Vietnamese Dong."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 12)
        kwargs.setdefault('decimal_places', 0)
        kwargs.setdefault('min_value', 0)
        super().__init__(**kwargs)


class PhoneField(serializers.CharField):
    """Serializer field for Vietnamese phone numbers."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 15)
        super().__init__(**kwargs)
    
    def to_internal_value(self, data):
        from .validators import normalize_phone, validate_vietnamese_phone
        
        value = super().to_internal_value(data)
        normalized = normalize_phone(value)
        
        if not validate_vietnamese_phone(normalized):
            raise serializers.ValidationError('Số điện thoại không hợp lệ')
        
        return normalized


class SlugField(serializers.SlugField):
    """Serializer field for slugs with validation."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 255)
        kwargs.setdefault('allow_unicode', False)
        super().__init__(**kwargs)


# ==================== Response Serializers ====================

class SuccessResponseSerializer(serializers.Serializer):
    """Standard success response."""
    success = serializers.BooleanField(default=True)
    message = serializers.CharField(required=False)


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField(required=False)


class PaginatedResponseSerializer(serializers.Serializer):
    """Standard paginated response."""
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    results = serializers.ListField()
