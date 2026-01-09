"""Users Security - Production-Ready Models."""
import secrets
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.common.core.models import TimeStampedModel, UUIDModel


class TwoFactorConfig(TimeStampedModel):
    """Two-Factor Authentication configuration."""

    class Method(models.TextChoices):
        TOTP = 'totp', 'Authenticator App'
        EMAIL = 'email', 'Email OTP'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='two_factor')
    is_enabled = models.BooleanField(default=False, verbose_name='Enabled')
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.TOTP)
    secret = models.CharField(max_length=64, blank=True)
    backup_codes = models.JSONField(default=list, blank=True)
    backup_codes_count = models.PositiveSmallIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    setup_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '2FA Config'
        verbose_name_plural = '2FA Configs'

    def __str__(self) -> str:
        return f"2FA for {self.user.email} ({'Enabled' if self.is_enabled else 'Disabled'})"

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at', 'updated_at'])


class LoginAttempt(TimeStampedModel):
    """Audit log for login attempts."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_attempts')
    email = models.EmailField(verbose_name='Email')
    ip_address = models.GenericIPAddressField(verbose_name='IP Address')
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(verbose_name='Success')
    failure_reason = models.CharField(max_length=50, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['email', '-created_at']), models.Index(fields=['ip_address', '-created_at'])]

    def __str__(self) -> str:
        return f"{'✓' if self.success else '✗'} {self.email} from {self.ip_address}"


class AccountLockout(TimeStampedModel):
    """Account lockout tracking."""

    class Reason(models.TextChoices):
        FAILED_LOGINS = 'failed_logins', 'Failed Logins'
        SUSPICIOUS_ACTIVITY = 'suspicious', 'Suspicious Activity'
        ADMIN_ACTION = 'admin', 'Admin Action'
        BRUTE_FORCE = 'brute_force', 'Brute Force Attack'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lockouts')
    reason = models.CharField(max_length=20, choices=Reason.choices)
    locked_until = models.DateTimeField(verbose_name='Locked Until')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='unlocked_accounts')

    class Meta:
        verbose_name = 'Account Lockout'
        verbose_name_plural = 'Account Lockouts'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Lockout: {self.user.email} until {self.locked_until}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.locked_until

    def unlock(self, unlocked_by=None):
        self.is_active = False
        self.unlocked_at = timezone.now()
        self.unlocked_by = unlocked_by
        self.save(update_fields=['is_active', 'unlocked_at', 'unlocked_by', 'updated_at'])


class APIKey(UUIDModel):
    """API keys for programmatic access."""

    class Permission(models.TextChoices):
        READ = 'read', 'Read Only'
        WRITE = 'write', 'Read/Write'
        ADMIN = 'admin', 'Admin'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, verbose_name='Name')
    key_prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64)
    permission = models.CharField(max_length=10, choices=Permission.choices, default=Permission.READ)
    allowed_ips = models.JSONField(default=list, blank=True)
    rate_limit = models.PositiveIntegerField(default=1000)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
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
        plain_key = f"owls_{secrets.token_urlsafe(32)}"
        key_prefix = plain_key[:12]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        expires_at = timezone.now() + timedelta(days=expires_days) if expires_days else None
        api_key = cls.objects.create(user=user, name=name, key_prefix=key_prefix, key_hash=key_hash, permission=permission, expires_at=expires_at)
        return api_key, plain_key

    @classmethod
    def verify(cls, plain_key: str):
        if not plain_key.startswith('owls_'):
            return None
        key_prefix = plain_key[:12]
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        try:
            api_key = cls.objects.get(key_prefix=key_prefix, key_hash=key_hash, is_active=True)
            if api_key.expires_at and timezone.now() > api_key.expires_at:
                return None
            api_key.last_used_at = timezone.now()
            api_key.usage_count += 1
            api_key.save(update_fields=['last_used_at', 'usage_count'])
            return api_key
        except cls.DoesNotExist:
            return None

    def revoke(self):
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class TrustedDevice(TimeStampedModel):
    """Trusted devices for bypassing 2FA."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trusted_devices')
    device_token = models.CharField(max_length=64, unique=True, db_index=True)
    device_fingerprint = models.CharField(max_length=64, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    trusted_at = models.DateTimeField(auto_now_add=True)
    trusted_until = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trusted Device'
        verbose_name_plural = 'Trusted Devices'
        ordering = ['-last_used']

    def __str__(self) -> str:
        return f"{self.user.email}: {self.device_name or self.device_type}"

    @property
    def is_valid(self) -> bool:
        return self.is_active and timezone.now() < self.trusted_until

    def revoke(self):
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class IPBlacklist(TimeStampedModel):
    """IP address blacklist for blocking malicious IPs."""

    class Reason(models.TextChoices):
        BRUTE_FORCE = 'brute_force', 'Brute Force'
        SPAM = 'spam', 'Spam'
        ABUSE = 'abuse', 'Abuse'
        FRAUD = 'fraud', 'Fraud'
        MANUAL = 'manual', 'Manual'

    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(blank=True)
    blocked_until = models.DateTimeField(null=True, blank=True)
    is_permanent = models.BooleanField(default=False)
    block_count = models.PositiveIntegerField(default=0)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

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
        blocked_until = None if permanent else timezone.now() + timedelta(hours=hours)
        entry, created = cls.objects.update_or_create(
            ip_address=ip_address,
            defaults={'reason': reason, 'blocked_until': blocked_until, 'is_permanent': permanent, 'added_by': added_by}
        )
        if not created:
            entry.block_count += 1
            entry.save(update_fields=['block_count'])
        return entry


class SecurityAuditLog(TimeStampedModel):
    """Comprehensive security audit log."""

    class EventType(models.TextChoices):
        LOGIN_SUCCESS = 'login_success', 'Login Success'
        LOGIN_FAILED = 'login_failed', 'Login Failed'
        LOGOUT = 'logout', 'Logout'
        TWO_FA_ENABLED = '2fa_enabled', '2FA Enabled'
        TWO_FA_DISABLED = '2fa_disabled', '2FA Disabled'
        PASSWORD_CHANGED = 'password_changed', 'Password Changed'
        PASSWORD_RESET = 'password_reset', 'Password Reset'
        ACCOUNT_LOCKED = 'account_locked', 'Account Locked'
        ACCOUNT_UNLOCKED = 'account_unlocked', 'Account Unlocked'
        API_KEY_CREATED = 'api_key_created', 'API Key Created'
        API_KEY_REVOKED = 'api_key_revoked', 'API Key Revoked'
        SUSPICIOUS_ACTIVITY = 'suspicious', 'Suspicious Activity'
        IP_BLOCKED = 'ip_blocked', 'IP Blocked'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='security_audits')
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=10, default='info', choices=[('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical')])

    class Meta:
        verbose_name = 'Security Audit Log'
        verbose_name_plural = 'Security Audit Logs'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at']), models.Index(fields=['event_type', '-created_at'])]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} - {self.user.email if self.user else 'N/A'}"

    @classmethod
    def log(cls, event_type: str, user=None, ip_address: str = None, description: str = '', metadata: dict = None, severity: str = 'info'):
        return cls.objects.create(event_type=event_type, user=user, ip_address=ip_address, description=description, metadata=metadata or {}, severity=severity)


class CSPReport(TimeStampedModel):
    """Content Security Policy violation reports."""

    document_uri = models.URLField(max_length=500)
    violated_directive = models.CharField(max_length=100)
    blocked_uri = models.TextField(blank=True)
    source_file = models.CharField(max_length=500, blank=True)
    line_number = models.PositiveIntegerField(null=True, blank=True)
    column_number = models.PositiveIntegerField(null=True, blank=True)
    original_policy = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'CSP Report'
        verbose_name_plural = 'CSP Reports'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.violated_directive}: {self.blocked_uri[:50]}"
