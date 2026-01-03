"""
Users Identity - Domain Models.

Core identity models for the e-commerce platform:
- User: Custom user with UUID, email-based auth
- UserAddress: Multiple shipping addresses per user
- SocialAccount: OAuth provider links
"""
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.common.core.models import TimeStampedModel, SoftDeleteManager
from apps.common.core.validators import phone_validator


class UserManager(BaseUserManager):
    """
    Custom user manager supporting email-based authentication.
    """
    
    def _create_user(self, email: str, password: str, **extra_fields):
        """Create and save a user with email and password."""
        if not email:
            raise ValueError('Email là bắt buộc')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_user(self, email: str, password: str = None, **extra_fields):
        """Create a regular user."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)
    
    def create_superuser(self, email: str, password: str, **extra_fields):
        """Create a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_email_verified', True)
        
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser phải có is_staff=True')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser phải có is_superuser=True')
        
        return self._create_user(email, password, **extra_fields)
    
    def get_queryset(self):
        """Exclude soft-deleted users by default."""
        return super().get_queryset().filter(is_deleted=False)
    
    def with_deleted(self):
        """Include soft-deleted users."""
        return super().get_queryset()


class User(AbstractUser):
    """
    Custom User model - Aggregate Root for Identity context.
    
    Features:
    - UUID primary key
    - Email-based authentication
    - Phone number with validation
    - Soft delete support
    - GHN address integration
    """
    
    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Authentication - email is primary
    email = models.EmailField(
        unique=True,
        verbose_name='Email',
        error_messages={'unique': 'Email này đã được sử dụng'}
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        verbose_name='Username'
    )
    
    # Profile
    phone = models.CharField(
        max_length=15,
        blank=True,
        validators=[phone_validator],
        verbose_name='Số điện thoại'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Ảnh đại diện'
    )
    
    # Default address (text for display)
    address = models.TextField(blank=True, verbose_name='Địa chỉ')
    ward = models.CharField(max_length=100, blank=True, verbose_name='Phường/Xã')
    district = models.CharField(max_length=100, blank=True, verbose_name='Quận/Huyện')
    city = models.CharField(max_length=100, blank=True, verbose_name='Tỉnh/Thành phố')
    
    # GHN Address IDs (for shipping API)
    province_id = models.IntegerField(
        null=True, blank=True,
        help_text='GHN Province ID'
    )
    district_id = models.IntegerField(
        null=True, blank=True,
        help_text='GHN District ID'
    )
    ward_code = models.CharField(
        max_length=20, blank=True,
        help_text='GHN Ward Code'
    )
    
    # Email verification
    is_email_verified = models.BooleanField(
        default=False,
        verbose_name='Email đã xác thực'
    )
    email_verified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời điểm xác thực email'
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Manager
    objects = UserManager()
    
    # Auth settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'Người dùng'
        verbose_name_plural = 'Người dùng'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self) -> str:
        return self.email
    
    def save(self, *args, **kwargs):
        import secrets
        # Auto-generate username from email if not provided
        if not self.username:
            base_username = self.email.split('@')[0][:30]  # Limit base length
            
            # Try original username first
            if not User.objects.with_deleted().filter(username=base_username).exists():
                self.username = base_username
            else:
                # Use random suffix instead of N+1 loop
                for _ in range(10):  # Max 10 attempts
                    random_suffix = secrets.token_hex(3)  # 6 hex chars
                    username = f"{base_username}_{random_suffix}"
                    if not User.objects.with_deleted().filter(username=username).exists():
                        self.username = username
                        break
                else:
                    # Fallback to UUID if all attempts fail
                    self.username = f"{base_username}_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    # --- Domain Methods ---
    
    @property
    def full_name(self) -> str:
        """Get user's full name or fallback to username."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username
    
    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))
    
    @property
    def has_complete_profile(self) -> bool:
        """Check if user has completed their profile."""
        return all([
            self.first_name,
            self.phone,
            self.address,
            self.district_id,
            self.ward_code
        ])
    
    def verify_email(self) -> None:
        """Mark email as verified."""
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=['is_email_verified', 'email_verified_at', 'updated_at'])
    
    def soft_delete(self) -> None:
        """
        Soft delete user account.
        
        - Marks as deleted
        - Anonymizes email/username for re-registration
        - Deactivates account
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        
        # Anonymize identifiers
        deleted_suffix = f"deleted_{self.id}"
        self.email = f"{deleted_suffix}@deleted.local"
        self.username = deleted_suffix
        
        self.save(update_fields=[
            'is_deleted', 'deleted_at', 'is_active',
            'email', 'username', 'updated_at'
        ])
    
    def update_profile(self, **kwargs) -> None:
        """Update profile fields."""
        allowed_fields = [
            'first_name', 'last_name', 'phone', 'avatar',
            'address', 'ward', 'district', 'city',
            'province_id', 'district_id', 'ward_code'
        ]
        
        update_fields = ['updated_at']
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
                update_fields.append(field)
        
        if len(update_fields) > 1:
            self.save(update_fields=update_fields)


class UserAddress(TimeStampedModel):
    """
    Shipping address entity - part of User aggregate.
    
    Users can have multiple shipping addresses with one default.
    Stores both display text and GHN IDs for shipping integration.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name='Người dùng'
    )
    
    # Label
    label = models.CharField(
        max_length=50,
        default='Home',
        verbose_name='Nhãn',
        help_text='Ví dụ: Nhà, Công ty'
    )
    
    # Recipient info
    recipient_name = models.CharField(
        max_length=100,
        verbose_name='Tên người nhận'
    )
    phone = models.CharField(
        max_length=15,
        validators=[phone_validator],
        verbose_name='Số điện thoại'
    )
    
    # Address components
    street = models.CharField(
        max_length=255,
        verbose_name='Địa chỉ chi tiết'
    )
    ward = models.CharField(
        max_length=100,
        verbose_name='Phường/Xã'
    )
    district = models.CharField(
        max_length=100,
        verbose_name='Quận/Huyện'
    )
    city = models.CharField(
        max_length=100,
        verbose_name='Tỉnh/Thành phố'
    )
    
    # GHN IDs for shipping API
    province_id = models.IntegerField(
        verbose_name='Mã tỉnh GHN'
    )
    district_id = models.IntegerField(
        verbose_name='Mã quận GHN'
    )
    ward_code = models.CharField(
        max_length=20,
        verbose_name='Mã phường GHN'
    )
    
    # Default flag
    is_default = models.BooleanField(
        default=False,
        verbose_name='Địa chỉ mặc định'
    )
    
    class Meta:
        verbose_name = 'Địa chỉ giao hàng'
        verbose_name_plural = 'Địa chỉ giao hàng'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self) -> str:
        return f"{self.label} - {self.recipient_name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default:
            UserAddress.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        elif not UserAddress.objects.filter(user=self.user).exists():
            # First address is always default
            self.is_default = True
        
        super().save(*args, **kwargs)
    
    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.street, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))
    
    def set_as_default(self) -> None:
        """Set this address as the default."""
        if not self.is_default:
            self.is_default = True
            self.save(update_fields=['is_default', 'updated_at'])


class SocialAccount(TimeStampedModel):
    """
    Linked social account for OAuth authentication.
    
    Supports:
    - GitHub
    - Google
    """
    
    class Provider(models.TextChoices):
        GITHUB = 'github', 'GitHub'
        GOOGLE = 'google', 'Google'
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='social_accounts',
        verbose_name='Người dùng'
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        verbose_name='Nhà cung cấp'
    )
    uid = models.CharField(
        max_length=255,
        verbose_name='Provider User ID'
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Dữ liệu bổ sung'
    )
    
    class Meta:
        verbose_name = 'Tài khoản liên kết'
        verbose_name_plural = 'Tài khoản liên kết'
        unique_together = ['provider', 'uid']
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_provider_display()}"


class UserSession(TimeStampedModel):
    """
    Track active user sessions for security.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='Người dùng'
    )
    
    # Session identification
    session_key = models.CharField(max_length=64, unique=True, db_index=True)
    refresh_token_hash = models.CharField(max_length=64, blank=True)
    
    # Device info
    device_type = models.CharField(max_length=20, blank=True)  # mobile, tablet, desktop
    device_name = models.CharField(max_length=100, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    
    # Location
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = 'Phiên đăng nhập'
        verbose_name_plural = 'Phiên đăng nhập'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.device_name or self.device_type}"
    
    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
    
    @property
    def is_current(self) -> bool:
        """Check if this is the current session."""
        return self.is_active and not self.is_expired
    
    def terminate(self) -> None:
        """Terminate this session."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def refresh_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    @classmethod
    def terminate_all_for_user(cls, user, except_session_key: str = None) -> int:
        """Terminate all sessions for a user."""
        queryset = cls.objects.filter(user=user, is_active=True)
        if except_session_key:
            queryset = queryset.exclude(session_key=except_session_key)
        return queryset.update(is_active=False)


class LoginHistory(TimeStampedModel):
    """
    Audit log for login attempts.
    """
    
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Thành công'
        FAILED = 'failed', 'Thất bại'
        BLOCKED = 'blocked', 'Bị chặn'
    
    class FailReason(models.TextChoices):
        INVALID_PASSWORD = 'invalid_password', 'Sai mật khẩu'
        ACCOUNT_LOCKED = 'account_locked', 'Tài khoản bị khóa'
        ACCOUNT_INACTIVE = 'account_inactive', 'Tài khoản không hoạt động'
        EMAIL_NOT_VERIFIED = 'email_not_verified', 'Email chưa xác thực'
        CAPTCHA_FAILED = 'captcha_failed', 'CAPTCHA không hợp lệ'
        RATE_LIMITED = 'rate_limited', 'Quá nhiều lần thử'
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_history',
        verbose_name='Người dùng'
    )
    email = models.EmailField(verbose_name='Email đăng nhập')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        verbose_name='Trạng thái'
    )
    fail_reason = models.CharField(
        max_length=30,
        choices=FailReason.choices,
        blank=True,
        verbose_name='Lý do thất bại'
    )
    
    # Device info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    
    # Location
    location = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    
    class Meta:
        verbose_name = 'Lịch sử đăng nhập'
        verbose_name_plural = 'Lịch sử đăng nhập'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['email', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.email} - {self.get_status_display()}"


class UserPreferences(TimeStampedModel):
    """
    User preferences and settings.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences',
        primary_key=True
    )
    
    # Notifications
    email_notifications = models.BooleanField(default=True, verbose_name='Email thông báo')
    order_updates = models.BooleanField(default=True, verbose_name='Cập nhật đơn hàng')
    promotional_emails = models.BooleanField(default=False, verbose_name='Email khuyến mãi')
    newsletter = models.BooleanField(default=False, verbose_name='Bản tin')
    
    # Push notifications
    push_notifications = models.BooleanField(default=True, verbose_name='Push')
    push_order_updates = models.BooleanField(default=True)
    push_promotions = models.BooleanField(default=False)
    
    # SMS
    sms_notifications = models.BooleanField(default=False, verbose_name='SMS')
    sms_order_updates = models.BooleanField(default=True)
    
    # Display
    language = models.CharField(max_length=10, default='vi', verbose_name='Ngôn ngữ')
    currency = models.CharField(max_length=3, default='VND', verbose_name='Tiền tệ')
    timezone_name = models.CharField(max_length=50, default='Asia/Ho_Chi_Minh')
    
    # Privacy
    profile_visibility = models.CharField(
        max_length=20,
        default='private',
        choices=[
            ('public', 'Công khai'),
            ('private', 'Riêng tư'),
        ]
    )
    show_order_history = models.BooleanField(default=False)
    allow_review_public = models.BooleanField(default=True)
    
    # Security
    two_factor_enabled = models.BooleanField(default=False, verbose_name='2FA')
    login_notification = models.BooleanField(default=True, verbose_name='Thông báo đăng nhập')
    
    class Meta:
        verbose_name = 'Cài đặt người dùng'
        verbose_name_plural = 'Cài đặt người dùng'
    
    def __str__(self) -> str:
        return f"Preferences for {self.user.email}"


class AccountDeletionRequest(TimeStampedModel):
    """
    Request for account deletion (GDPR compliance).
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Đang chờ'
        APPROVED = 'approved', 'Đã duyệt'
        COMPLETED = 'completed', 'Hoàn thành'
        CANCELLED = 'cancelled', 'Đã hủy'
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deletion_requests',
        verbose_name='Người dùng'
    )
    
    # Request details
    reason = models.TextField(blank=True, verbose_name='Lý do')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Trạng thái'
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Lên lịch xóa'
    )
    grace_period_days = models.PositiveIntegerField(
        default=30,
        verbose_name='Ngày ân hạn'
    )
    
    # Processing
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Người xử lý'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Data export
    data_exported = models.BooleanField(default=False)
    export_url = models.URLField(blank=True)
    
    class Meta:
        verbose_name = 'Yêu cầu xóa tài khoản'
        verbose_name_plural = 'Yêu cầu xóa tài khoản'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.scheduled_at and self.status == self.Status.PENDING:
            from datetime import timedelta
            self.scheduled_at = timezone.now() + timedelta(days=self.grace_period_days)
        super().save(*args, **kwargs)
    
    def cancel(self) -> None:
        """Cancel the deletion request."""
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
    
    def approve(self, admin_user=None) -> None:
        """Approve the deletion request."""
        self.status = self.Status.APPROVED
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_by', 'processed_at', 'updated_at'])
    
    def execute(self) -> None:
        """Execute account deletion."""
        self.user.soft_delete()
        self.status = self.Status.COMPLETED
        self.save(update_fields=['status', 'updated_at'])
