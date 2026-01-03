"""
Users Security - Serializers.

DTOs for security API.
"""
from rest_framework import serializers
from .models import (
    TwoFactorConfig, LoginAttempt, AccountLockout,
    APIKey, TrustedDevice, SecurityAuditLog
)


# ==================== 2FA Serializers ====================

class TwoFactorStatusSerializer(serializers.ModelSerializer):
    """2FA status output."""
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    
    class Meta:
        model = TwoFactorConfig
        fields = ['is_enabled', 'method', 'method_display', 'last_used_at', 'backup_codes_count']


class TwoFactorSetupSerializer(serializers.Serializer):
    """2FA setup output."""
    secret = serializers.CharField()
    qr_code_uri = serializers.CharField()
    backup_codes = serializers.ListField(child=serializers.CharField())


class TwoFactorEnableSerializer(serializers.Serializer):
    """2FA enable input."""
    code = serializers.CharField(min_length=6, max_length=6)


class TwoFactorVerifySerializer(serializers.Serializer):
    """2FA verification input."""
    code = serializers.CharField(max_length=20)  # TOTP or backup code
    trust_device = serializers.BooleanField(default=False)
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class TwoFactorDisableSerializer(serializers.Serializer):
    """2FA disable input."""
    password = serializers.CharField()


class BackupCodesSerializer(serializers.Serializer):
    """Backup codes output."""
    backup_codes = serializers.ListField(child=serializers.CharField())
    remaining = serializers.IntegerField()


class RegenerateBackupCodesSerializer(serializers.Serializer):
    """Regenerate backup codes input."""
    password = serializers.CharField()


# ==================== API Key Serializers ====================

class APIKeySerializer(serializers.ModelSerializer):
    """API key output (without full key)."""
    permission_display = serializers.CharField(source='get_permission_display', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'key_prefix', 'permission', 'permission_display',
            'allowed_ips', 'rate_limit',
            'is_active', 'expires_at', 'is_expired',
            'last_used_at', 'usage_count', 'created_at'
        ]
    
    def get_is_expired(self, obj):
        if obj.expires_at:
            from django.utils import timezone
            return timezone.now() > obj.expires_at
        return False


class APIKeyCreateSerializer(serializers.Serializer):
    """API key creation input."""
    name = serializers.CharField(max_length=100)
    permission = serializers.ChoiceField(choices=APIKey.Permission.choices, default='read')
    allowed_ips = serializers.ListField(
        child=serializers.IPAddressField(),
        required=False,
        default=list
    )
    rate_limit = serializers.IntegerField(min_value=100, max_value=100000, default=1000)
    expires_days = serializers.IntegerField(min_value=1, max_value=365, required=False)


class APIKeyCreatedSerializer(serializers.Serializer):
    """API key created output (includes full key once)."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    key = serializers.CharField()  # Full key - only shown once!
    permission = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)


# ==================== Trusted Device Serializers ====================

class TrustedDeviceSerializer(serializers.ModelSerializer):
    """Trusted device output."""
    is_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = TrustedDevice
        fields = [
            'id', 'device_name', 'device_type', 'browser', 'os',
            'ip_address', 'location',
            'trusted_at', 'trusted_until', 'is_valid', 'is_active', 'last_used'
        ]


# ==================== Login History Serializers ====================

class LoginAttemptSerializer(serializers.ModelSerializer):
    """Login attempt output."""
    
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'email', 'ip_address', 'device_type', 'browser', 'os',
            'country', 'city',
            'success', 'failure_reason',
            'required_2fa', 'passed_2fa',
            'created_at'
        ]


# ==================== Audit Log Serializers ====================

class SecurityAuditLogSerializer(serializers.ModelSerializer):
    """Security audit log output."""
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = SecurityAuditLog
        fields = [
            'id', 'event_type', 'event_type_display',
            'description', 'severity',
            'ip_address', 'location',
            'metadata', 'created_at'
        ]


# ==================== Account Lockout Serializers ====================

class AccountLockoutSerializer(serializers.ModelSerializer):
    """Account lockout output."""
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = AccountLockout
        fields = [
            'id', 'reason', 'reason_display',
            'locked_until', 'is_expired', 'is_active',
            'unlocked_at', 'created_at'
        ]
