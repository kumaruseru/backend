"""Users Security - Serializers."""
from rest_framework import serializers
from .models import TwoFactorConfig, APIKey, TrustedDevice, LoginAttempt, SecurityAuditLog


class TwoFactorStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwoFactorConfig
        fields = ['is_enabled', 'method', 'backup_codes_count', 'last_used_at']


class TwoFactorSetupSerializer(serializers.Serializer):
    secret = serializers.CharField()
    qr_code = serializers.CharField()
    backup_codes = serializers.ListField(child=serializers.CharField())


class TwoFactorEnableSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)


class TwoFactorVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)
    temp_token = serializers.CharField(required=False)


class TwoFactorDisableSerializer(serializers.Serializer):
    password = serializers.CharField()


class BackupCodesSerializer(serializers.Serializer):
    remaining = serializers.IntegerField()


class RegenerateBackupCodesSerializer(serializers.Serializer):
    password = serializers.CharField()


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ['id', 'name', 'key_prefix', 'permission', 'is_active', 'expires_at', 'last_used_at', 'usage_count', 'created_at']


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    permission = serializers.ChoiceField(choices=APIKey.Permission.choices, default='read')
    expires_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    allowed_ips = serializers.ListField(child=serializers.CharField(), required=False)
    rate_limit = serializers.IntegerField(required=False, min_value=1, max_value=100000)


class APIKeyCreatedSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    key = serializers.CharField()
    permission = serializers.CharField()
    expires_at = serializers.DateTimeField()


class TrustedDeviceSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = TrustedDevice
        fields = ['id', 'device_name', 'device_type', 'browser', 'os', 'ip_address', 'location', 'is_active', 'is_valid', 'trusted_at', 'trusted_until', 'last_used']


class LoginAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = ['id', 'email', 'ip_address', 'success', 'failure_reason', 'device_type', 'browser', 'os', 'country', 'city', 'created_at']


class SecurityAuditLogSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = SecurityAuditLog
        fields = ['id', 'event_type', 'event_display', 'description', 'ip_address', 'location', 'severity', 'created_at']
