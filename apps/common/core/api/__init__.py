"""Common Core API Package."""
from .pagination import StandardPagination, SmallPagination, LargePagination, paginate_queryset
from .permissions import IsOwner, IsOwnerOrAdmin, IsOwnerOrReadOnly, IsAdminOrReadOnly, IsVerifiedUser, IsSuperUser, DenyAll
from .handlers import custom_exception_handler
from .serializers import (
    TimestampsMixin, SoftDeleteMixin, DynamicFieldsSerializer, WriteOnceFieldsMixin,
    MoneyField, VietnamPhoneField, SlugField, SuccessResponseSerializer, ErrorResponseSerializer
)

__all__ = [
    'StandardPagination', 'SmallPagination', 'LargePagination', 'paginate_queryset',
    'IsOwner', 'IsOwnerOrAdmin', 'IsOwnerOrReadOnly', 'IsAdminOrReadOnly', 'IsVerifiedUser', 'IsSuperUser', 'DenyAll',
    'custom_exception_handler',
    'TimestampsMixin', 'SoftDeleteMixin', 'DynamicFieldsSerializer', 'WriteOnceFieldsMixin',
    'MoneyField', 'VietnamPhoneField', 'SlugField', 'SuccessResponseSerializer', 'ErrorResponseSerializer',
]
