"""
Users Security - Production-Ready Models.

Comprehensive security models for:
- TwoFactorConfig: 2FA with TOTP/Email
- LoginAttempt: Login auditing
- AccountLockout: Account protection
- APIKey: API key management
- TrustedDevice: Device fingerprinting
- IPBlacklist: IP-based blocking
- SecurityAuditLog: Security event logging
"""
import secrets
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from apps.common.core.models import TimeStampedModel, UUIDModel


class TwoFactorConfig(TimeStampedModel):
    """
    Two-Factor Authentication configuration.
    
    Supports:
    - TOTP (Authenticator apps)
    - Email OTP
    - SMS OTP (future)
    """
    
    class Method(models.TextChoices):
        TOTP = 'totp', 'Authenticator App'
        EMAIL = 'email', 'Email OTP'
        SMS = 'sms', 'SMS OTP'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='two_factor',
        verbose_name='Người dùng'
    )
    
    is_enabled = models.BooleanField(default=False, verbose_name='Đã kích hoạt')
    method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.TOTP,
        verbose_name='Phương thức'
    )
    
    # TOTP secret (should be encrypted in production)
    secret = models.CharField(max_length=64, blank=True, verbose_name='Secret Key')
    
    # Backup codes (hashed)
    backup_codes = models.JSONField(default=list, blank=True, verbose_name='Mã dự phòng')
    backup_codes_count = models.PositiveSmallIntegerField(default=0)
    
    # Tracking
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Sử dụng lần cuối')
    setup_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Recovery
    recovery_email = models.EmailField(blank=True, verbose_name='Email khôi phục')
    recovery_phone = models.CharField(max_length=15, blank=True, verbose_name='SĐT khôi phục')
    
    class Meta:
        verbose_name = 'Cấu hình 2FA'
        verbose_name_plural = 'Cấu hình 2FA'
    
    def __str__(self) -> str:
        status = 'Enabled' if self.is_enabled else 'Disabled'
        return f"2FA for {self.user.email} ({status})"
    
    def mark_used(self):
        """Update last used timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at', 'updated_at'])


class LoginAttempt(TimeStampedModel):
    """
    Audit log for login attempts.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='login_attempts',
        verbose_name='Người dùng'
    )
    email = models.EmailField(verbose_name='Email')
    ip_address = models.GenericIPAddressField(verbose_name='Địa chỉ IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    
    success = models.BooleanField(verbose_name='Thành công')
    failure_reason = models.CharField(max_length=50, blank=True, verbose_name='Lý do thất bại')
    
    # Device info
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    
    # Location
    country = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # 2FA
    required_2fa = models.BooleanField(default=False)
    passed_2fa = models.BooleanField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Lịch sử đăng nhập'
        verbose_name_plural = 'Lịch sử đăng nhập'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self) -> str:
        status = '✓' if self.success else '✗'
        return f"{status} {self.email} from {self.ip_address}"


class AccountLockout(TimeStampedModel):
    """
    Account lockout tracking.
    """
    
    class Reason(models.TextChoices):
        FAILED_LOGINS = 'failed_logins', 'Đăng nhập sai nhiều lần'
        SUSPICIOUS_ACTIVITY = 'suspicious', 'Hoạt động đáng ngờ'
        ADMIN_ACTION = 'admin', 'Khóa bởi admin'
        BRUTE_FORCE = 'brute_force', 'Tấn công brute force'
        COMPROMISED = 'compromised', 'Tài khoản bị xâm phạm'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lockouts',
        verbose_name='Người dùng'
    )
    
    reason = models.CharField(max_length=20, choices=Reason.choices, verbose_name='Lý do')
    locked_until = models.DateTimeField(verbose_name='Khóa đến')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='unlocked_accounts'
    )
    
    class Meta:
        verbose_name = 'Khóa tài khoản'
        verbose_name_plural = 'Khóa tài khoản'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"Lockout: {self.user.email} until {self.locked_until}"
    
    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.locked_until
    
    def unlock(self, unlocked_by=None):
        """Unlock the account."""
        self.is_active = False
        self.unlocked_at = timezone.now()
        self.unlocked_by = unlocked_by
        self.save(update_fields=['is_active', 'unlocked_at', 'unlocked_by', 'updated_at'])


class APIKey(UUIDModel):
    """
    API keys for programmatic access.
    """
    
    class Permission(models.TextChoices):
        READ = 'read', 'Read Only'
        WRITE = 'write', 'Read/Write'
        ADMIN = 'admin', 'Admin'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='Người dùng'
    )
    
    name = models.CharField(max_length=100, verbose_name='Tên')
    key_prefix = models.CharField(max_length=8, db_index=True)  # First 8 chars for lookup
    key_hash = models.CharField(max_length=64)  # SHA-256 hash
    
    permission = models.CharField(
        max_length=10,
        choices=Permission.choices,
        default=Permission.READ,
        verbose_name='Quyền'
    )
    
    # Restrictions
    allowed_ips = models.JSONField(default=list, blank=True)  # Empty = all IPs
    rate_limit = models.PositiveIntegerField(default=1000)  # requests per hour
    
    # Status
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix}...)"
    
    @classmethod
    def generate(cls, user, name: str, permission: str = 'read', expires_days: int = None) -> tuple:
        """
        Generate a new API key.
        
        Returns:
            Tuple of (APIKey instance, plain key string)
        """
        # Generate random key
        plain_key = f"owls_{secrets.token_urlsafe(32)}"
        key_prefix = plain_key[:12]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timedelta(days=expires_days)
        
        api_key = cls.objects.create(
            user=user,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            permission=permission,
            expires_at=expires_at
        )
        
        return api_key, plain_key
    
    @classmethod
    def verify(cls, plain_key: str):
        """
        Verify an API key and return the instance.
        """
        if not plain_key.startswith('owls_'):
            return None
        
        key_prefix = plain_key[:12]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        
        try:
            api_key = cls.objects.get(
                key_prefix=key_prefix,
                key_hash=key_hash,
                is_active=True
            )
            
            # Check expiration
            if api_key.expires_at and timezone.now() > api_key.expires_at:
                return None
            
            # Update usage
            api_key.last_used_at = timezone.now()
            api_key.usage_count += 1
            api_key.save(update_fields=['last_used_at', 'usage_count'])
            
            return api_key
            
        except cls.DoesNotExist:
            return None
    
    def revoke(self):
        """Revoke this API key."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class TrustedDevice(TimeStampedModel):
    """
    Trusted devices for bypassing 2FA.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trusted_devices',
        verbose_name='Người dùng'
    )
    
    # Device identification
    device_token = models.CharField(max_length=64, unique=True, db_index=True)
    device_fingerprint = models.CharField(max_length=64, blank=True)
    
    # Device info
    device_name = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    
    # Trust info
    trusted_at = models.DateTimeField(auto_now_add=True)
    trusted_until = models.DateTimeField()  # Trust expires
    
    # Location when trusted
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Thiết bị tin cậy'
        verbose_name_plural = 'Thiết bị tin cậy'
        ordering = ['-last_used']
    
    def __str__(self) -> str:
        return f"{self.user.email}: {self.device_name or self.device_type}"
    
    @property
    def is_valid(self) -> bool:
        return self.is_active and timezone.now() < self.trusted_until
    
    @classmethod
    def create_trust(cls, user, device_info: dict, trust_days: int = 30):
        """Create a new trusted device."""
        device_token = secrets.token_urlsafe(32)
        
        return cls.objects.create(
            user=user,
            device_token=device_token,
            device_fingerprint=device_info.get('fingerprint', ''),
            device_name=device_info.get('name', ''),
            device_type=device_info.get('type', ''),
            browser=device_info.get('browser', ''),
            os=device_info.get('os', ''),
            ip_address=device_info.get('ip'),
            location=device_info.get('location', ''),
            trusted_until=timezone.now() + timedelta(days=trust_days)
        ), device_token
    
    @classmethod
    def verify_trust(cls, user, device_token: str) -> bool:
        """Verify if device is trusted."""
        try:
            device = cls.objects.get(
                user=user,
                device_token=device_token,
                is_active=True
            )
            if device.is_valid:
                device.last_used = timezone.now()
                device.save(update_fields=['last_used'])
                return True
        except cls.DoesNotExist:
            pass
        return False
    
    def revoke(self):
        """Revoke trust for this device."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class IPBlacklist(TimeStampedModel):
    """
    IP address blacklist for blocking malicious IPs.
    """
    
    class Reason(models.TextChoices):
        BRUTE_FORCE = 'brute_force', 'Tấn công brute force'
        SPAM = 'spam', 'Spam'
        ABUSE = 'abuse', 'Lạm dụng'
        FRAUD = 'fraud', 'Gian lận'
        MANUAL = 'manual', 'Thêm thủ công'
    
    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(blank=True)
    
    # Blocking
    blocked_until = models.DateTimeField(null=True, blank=True)  # Null = permanent
    is_permanent = models.BooleanField(default=False)
    
    # Stats
    block_count = models.PositiveIntegerField(default=0)
    
    # Who added
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+'
    )
    
    class Meta:
        verbose_name = 'IP Blacklist'
        verbose_name_plural = 'IP Blacklist'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.ip_address} - {self.get_reason_display()}"
    
    @property
    def is_active(self) -> bool:
        if self.is_permanent:
            return True
        if self.blocked_until:
            return timezone.now() < self.blocked_until
        return True
    
    @classmethod
    def is_blocked(cls, ip_address: str) -> bool:
        """Check if an IP is blocked."""
        try:
            entry = cls.objects.get(ip_address=ip_address)
            if entry.is_active:
                entry.block_count += 1
                entry.save(update_fields=['block_count'])
                return True
        except cls.DoesNotExist:
            pass
        return False
    
    @classmethod
    def block_ip(cls, ip_address: str, reason: str, hours: int = 24, permanent: bool = False, added_by=None):
        """Block an IP address."""
        blocked_until = None if permanent else timezone.now() + timedelta(hours=hours)
        
        entry, created = cls.objects.update_or_create(
            ip_address=ip_address,
            defaults={
                'reason': reason,
                'blocked_until': blocked_until,
                'is_permanent': permanent,
                'added_by': added_by
            }
        )
        
        if not created:
            entry.block_count += 1
            entry.save(update_fields=['block_count'])
        
        return entry


class SecurityAuditLog(TimeStampedModel):
    """
    Comprehensive security audit log.
    """
    
    class EventType(models.TextChoices):
        # Authentication
        LOGIN_SUCCESS = 'login_success', 'Đăng nhập thành công'
        LOGIN_FAILED = 'login_failed', 'Đăng nhập thất bại'
        LOGOUT = 'logout', 'Đăng xuất'
        
        # 2FA
        TWO_FA_ENABLED = '2fa_enabled', 'Bật 2FA'
        TWO_FA_DISABLED = '2fa_disabled', 'Tắt 2FA'
        TWO_FA_VERIFIED = '2fa_verified', 'Xác thực 2FA'
        TWO_FA_FAILED = '2fa_failed', '2FA thất bại'
        BACKUP_CODE_USED = 'backup_used', 'Dùng mã dự phòng'
        
        # Account
        PASSWORD_CHANGED = 'password_changed', 'Đổi mật khẩu'
        PASSWORD_RESET = 'password_reset', 'Reset mật khẩu'
        EMAIL_CHANGED = 'email_changed', 'Đổi email'
        ACCOUNT_LOCKED = 'account_locked', 'Khóa tài khoản'
        ACCOUNT_UNLOCKED = 'account_unlocked', 'Mở khóa tài khoản'
        
        # API
        API_KEY_CREATED = 'api_key_created', 'Tạo API key'
        API_KEY_REVOKED = 'api_key_revoked', 'Thu hồi API key'
        
        # Devices
        DEVICE_TRUSTED = 'device_trusted', 'Trust thiết bị'
        DEVICE_REVOKED = 'device_revoked', 'Thu hồi trust'
        NEW_DEVICE_LOGIN = 'new_device', 'Login thiết bị mới'
        
        # Security
        SUSPICIOUS_ACTIVITY = 'suspicious', 'Hoạt động đáng ngờ'
        IP_BLOCKED = 'ip_blocked', 'Block IP'
        BRUTE_FORCE_DETECTED = 'brute_force', 'Phát hiện brute force'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='security_audits',
        verbose_name='Người dùng'
    )
    
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        db_index=True,
        verbose_name='Loại sự kiện'
    )
    description = models.TextField(blank=True, verbose_name='Mô tả')
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Severity
    severity = models.CharField(
        max_length=10,
        default='info',
        choices=[
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
        ]
    )
    
    class Meta:
        verbose_name = 'Security Audit Log'
        verbose_name_plural = 'Security Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_event_type_display()} - {self.user.email if self.user else 'N/A'}"
    
    @classmethod
    def log(cls, event_type: str, user=None, ip_address: str = None, 
            description: str = '', metadata: dict = None, severity: str = 'info'):
        """Log a security event."""
        return cls.objects.create(
            event_type=event_type,
            user=user,
            ip_address=ip_address,
            description=description,
            metadata=metadata or {},
            severity=severity
        )
