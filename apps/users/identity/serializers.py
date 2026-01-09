"""Users Identity - Serializers."""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserAddress, SocialAccount, UserSession, LoginHistory, UserPreferences


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email này đã được sử dụng')
        return value.lower()

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Mật khẩu xác nhận không khớp'})
        return attrs


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    captcha_token = serializers.CharField(required=False, allow_blank=True)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'full_name', 'phone', 'avatar',
                  'address', 'ward', 'district', 'city', 'province_id', 'district_id', 'ward_code',
                  'full_address', 'is_email_verified', 'date_joined', 'last_login']
        read_only_fields = ['id', 'email', 'is_email_verified', 'date_joined', 'last_login']


class UserProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    ward = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    province_id = serializers.IntegerField(required=False, allow_null=True)
    district_id = serializers.IntegerField(required=False, allow_null=True)
    ward_code = serializers.CharField(max_length=20, required=False, allow_blank=True)


class UserAddressSerializer(serializers.ModelSerializer):
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = UserAddress
        fields = ['id', 'label', 'recipient_name', 'phone', 'street', 'ward', 'district', 'city',
                  'province_id', 'district_id', 'ward_code', 'full_address', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserAddressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ['label', 'recipient_name', 'phone', 'street', 'ward', 'district', 'city',
                  'province_id', 'district_id', 'ward_code', 'is_default']

    def validate_phone(self, value: str) -> str:
        from apps.common.core.validators import validate_vietnamese_phone
        if not validate_vietnamese_phone(value):
            raise serializers.ValidationError('Số điện thoại không hợp lệ')
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Mật khẩu xác nhận không khớp'})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Mật khẩu xác nhận không khớp'})
        return attrs


class SocialAccountSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = SocialAccount
        fields = ['id', 'provider', 'provider_display', 'created_at']
        read_only_fields = ['id', 'provider', 'created_at']


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()


class UserSessionSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = UserSession
        fields = ['id', 'device_type', 'device_name', 'browser', 'os', 'ip_address', 'location',
                  'is_active', 'is_expired', 'last_activity', 'expires_at', 'created_at']


class LoginHistorySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LoginHistory
        fields = ['id', 'email', 'status', 'status_display', 'fail_reason', 'ip_address',
                  'device_type', 'browser', 'os', 'location', 'created_at']


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ['email_notifications', 'order_updates', 'promotional_emails', 'push_notifications',
                  'sms_notifications', 'language', 'currency', 'two_factor_enabled']


class UserPreferencesUpdateSerializer(serializers.Serializer):
    email_notifications = serializers.BooleanField(required=False)
    order_updates = serializers.BooleanField(required=False)
    promotional_emails = serializers.BooleanField(required=False)
    push_notifications = serializers.BooleanField(required=False)
    sms_notifications = serializers.BooleanField(required=False)
    language = serializers.CharField(max_length=10, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    two_factor_enabled = serializers.BooleanField(required=False)
