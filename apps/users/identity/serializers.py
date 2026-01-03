"""
Users Identity - Serializers.

DTOs for API input/output in the identity context.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserAddress, SocialAccount


class UserRegistrationSerializer(serializers.Serializer):
    """Registration input DTO."""
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    
    def validate_email(self, value: str) -> str:
        """Check email is not already registered."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email này đã được sử dụng')
        return value.lower()
    
    def validate_password(self, value: str) -> str:
        """Validate password strength."""
        validate_password(value)
        return value
    
    def validate(self, attrs: dict) -> dict:
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Mật khẩu xác nhận không khớp'
            })
        return attrs


class UserLoginSerializer(serializers.Serializer):
    """Login input DTO."""
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    captcha_token = serializers.CharField(required=False, allow_blank=True)


class UserSerializer(serializers.ModelSerializer):
    """User output DTO."""
    full_name = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()
    has_complete_profile = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username',
            'first_name', 'last_name', 'full_name',
            'phone', 'avatar',
            'address', 'ward', 'district', 'city',
            'province_id', 'district_id', 'ward_code',
            'full_address', 'has_complete_profile',
            'is_email_verified',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'is_email_verified', 'date_joined', 'last_login']


class UserProfileUpdateSerializer(serializers.Serializer):
    """Profile update input DTO."""
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    # Address fields
    address = serializers.CharField(required=False, allow_blank=True)
    ward = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # GHN IDs
    province_id = serializers.IntegerField(required=False, allow_null=True)
    district_id = serializers.IntegerField(required=False, allow_null=True)
    ward_code = serializers.CharField(max_length=20, required=False, allow_blank=True)


class UserAddressSerializer(serializers.ModelSerializer):
    """User address output DTO."""
    full_address = serializers.ReadOnlyField()
    
    class Meta:
        model = UserAddress
        fields = [
            'id', 'label',
            'recipient_name', 'phone',
            'street', 'ward', 'district', 'city',
            'province_id', 'district_id', 'ward_code',
            'full_address', 'is_default',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserAddressCreateSerializer(serializers.ModelSerializer):
    """Address creation input DTO."""
    
    class Meta:
        model = UserAddress
        fields = [
            'label',
            'recipient_name', 'phone',
            'street', 'ward', 'district', 'city',
            'province_id', 'district_id', 'ward_code',
            'is_default'
        ]
    
    def validate_phone(self, value: str) -> str:
        """Validate phone format."""
        from apps.common.core.validators import validate_vietnamese_phone
        if not validate_vietnamese_phone(value):
            raise serializers.ValidationError('Số điện thoại không hợp lệ')
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """Password change input DTO."""
    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_new_password(self, value: str) -> str:
        """Validate new password strength."""
        validate_password(value)
        return value
    
    def validate(self, attrs: dict) -> dict:
        """Validate password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Mật khẩu xác nhận không khớp'
            })
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Password reset request input DTO."""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Password reset confirmation input DTO."""
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_new_password(self, value: str) -> str:
        """Validate new password strength."""
        validate_password(value)
        return value
    
    def validate(self, attrs: dict) -> dict:
        """Validate password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Mật khẩu xác nhận không khớp'
            })
        return attrs


class SocialAccountSerializer(serializers.ModelSerializer):
    """Social account output DTO."""
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    
    class Meta:
        model = SocialAccount
        fields = ['id', 'provider', 'provider_display', 'created_at']
        read_only_fields = ['id', 'provider', 'created_at']


class TokenPairSerializer(serializers.Serializer):
    """JWT token pair output DTO."""
    access = serializers.CharField()
    refresh = serializers.CharField()


class EmailVerificationSerializer(serializers.Serializer):
    """Email verification input DTO."""
    token = serializers.CharField()


# ==================== Session & Security Serializers ====================

class UserSessionSerializer(serializers.ModelSerializer):
    """User session output DTO."""
    is_expired = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    
    class Meta:
        from .models import UserSession
        model = UserSession
        fields = [
            'id', 'device_type', 'device_name', 'browser', 'os',
            'ip_address', 'location',
            'is_active', 'is_expired', 'is_current',
            'last_activity', 'expires_at', 'created_at'
        ]


class LoginHistorySerializer(serializers.ModelSerializer):
    """Login history output DTO."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        from .models import LoginHistory
        model = LoginHistory
        fields = [
            'id', 'email', 'status', 'status_display', 'fail_reason',
            'ip_address', 'device_type', 'browser', 'os',
            'location', 'created_at'
        ]


class UserPreferencesSerializer(serializers.ModelSerializer):
    """User preferences output DTO."""
    
    class Meta:
        from .models import UserPreferences
        model = UserPreferences
        fields = [
            'email_notifications', 'order_updates', 'promotional_emails', 'newsletter',
            'push_notifications', 'push_order_updates', 'push_promotions',
            'sms_notifications', 'sms_order_updates',
            'language', 'currency', 'timezone_name',
            'profile_visibility', 'show_order_history', 'allow_review_public',
            'two_factor_enabled', 'login_notification'
        ]


class UserPreferencesUpdateSerializer(serializers.Serializer):
    """Preferences update input."""
    email_notifications = serializers.BooleanField(required=False)
    order_updates = serializers.BooleanField(required=False)
    promotional_emails = serializers.BooleanField(required=False)
    newsletter = serializers.BooleanField(required=False)
    push_notifications = serializers.BooleanField(required=False)
    push_order_updates = serializers.BooleanField(required=False)
    push_promotions = serializers.BooleanField(required=False)
    sms_notifications = serializers.BooleanField(required=False)
    sms_order_updates = serializers.BooleanField(required=False)
    language = serializers.CharField(max_length=10, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    timezone_name = serializers.CharField(max_length=50, required=False)
    profile_visibility = serializers.ChoiceField(choices=['public', 'private'], required=False)
    show_order_history = serializers.BooleanField(required=False)
    allow_review_public = serializers.BooleanField(required=False)
    two_factor_enabled = serializers.BooleanField(required=False)
    login_notification = serializers.BooleanField(required=False)


class AccountDeletionRequestSerializer(serializers.Serializer):
    """Account deletion request input."""
    reason = serializers.CharField(required=False, allow_blank=True)
    confirm = serializers.BooleanField()
    
    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError('Bạn phải xác nhận yêu cầu xóa tài khoản')
        return value


class AccountDeletionStatusSerializer(serializers.ModelSerializer):
    """Account deletion status output."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        from .models import AccountDeletionRequest
        model = AccountDeletionRequest
        fields = ['id', 'status', 'status_display', 'reason', 'scheduled_at', 'created_at']
