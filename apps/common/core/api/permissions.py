"""Common Core - DRF Permissions."""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Object-level permission to allow only owners to access."""

    def has_object_permission(self, request, view, obj):
        owner_field = getattr(view, 'owner_field', 'user')
        owner = getattr(obj, owner_field, None)
        if owner is None:
            return False
        return owner == request.user


class IsOwnerOrAdmin(permissions.BasePermission):
    """Allow owner or admin users."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner_field = getattr(view, 'owner_field', 'user')
        owner = getattr(obj, owner_field, None)
        return owner == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow owner to modify, others can only read."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner_field = getattr(view, 'owner_field', 'user')
        owner = getattr(obj, owner_field, None)
        return owner == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow admin to modify, others can only read."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsVerifiedUser(permissions.BasePermission):
    """Only allow verified users."""
    message = 'Email chưa được xác thực.'

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and getattr(request.user, 'is_email_verified', False)


class IsSuperUser(permissions.BasePermission):
    """Only allow superusers."""

    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


class DenyAll(permissions.BasePermission):
    """Deny all access (for disabled endpoints)."""

    def has_permission(self, request, view):
        return False
