"""Common Core API - Serializer Mixins."""
from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField


class TimestampsMixin(serializers.Serializer):
    """Mixin that adds timestamp fields."""
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class SoftDeleteMixin(serializers.Serializer):
    """Mixin for soft delete fields."""
    is_deleted = serializers.BooleanField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True)


class DynamicFieldsSerializer(serializers.Serializer):
    """Serializer that allows specifying which fields to include."""

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
    """Mixin that makes specified fields read-only after creation."""

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        write_once_fields = getattr(self.Meta, 'write_once_fields', [])
        if self.instance is not None:
            for field_name in write_once_fields:
                kwargs = extra_kwargs.get(field_name, {})
                kwargs['read_only'] = True
                extra_kwargs[field_name] = kwargs
        return extra_kwargs


class MoneyField(serializers.DecimalField):
    """Serializer field for Vietnamese Dong."""

    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 12)
        kwargs.setdefault('decimal_places', 0)
        kwargs.setdefault('min_value', 0)
        super().__init__(**kwargs)


class VietnamPhoneField(PhoneNumberField):
    """Serializer field for Vietnamese phone numbers using phonenumber_field."""

    def __init__(self, **kwargs):
        kwargs.setdefault('region', 'VN')
        super().__init__(**kwargs)


class SlugField(serializers.SlugField):
    """Serializer field for slugs with validation."""

    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 255)
        kwargs.setdefault('allow_unicode', False)
        super().__init__(**kwargs)


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
