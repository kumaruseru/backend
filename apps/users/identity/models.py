"""Users Identity - Domain Models."""
import uuid
import secrets
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from safedelete.models import SafeDeleteModel
from safedelete.config import SOFT_DELETE
from apps.common.core.models import TimeStampedModel
from apps.common.core.validators import phone_validator


class UserManager(BaseUserManager):
    """Custom user manager supporting email-based authentication."""

    def _create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str = None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_email_verified', True)
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with UUID, email-based auth, and soft delete."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name='Email', error_messages={'unique': 'This email is already in use'})
    username = models.CharField(max_length=150, unique=True, blank=True, verbose_name='Username')
    phone = models.CharField(max_length=15, blank=True, validators=[phone_validator], verbose_name='Phone Number')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Avatar')
    
    # Address fields - use raw_id_fields in admin for performance
    address = models.TextField(blank=True, verbose_name='Detailed Address')
    province = models.ForeignKey(
        'core.Province',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Province/City',
        related_name='users'
    )
    district = models.ForeignKey(
        'core.District',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='District',
        related_name='users'
    )
    ward = models.ForeignKey(
        'core.Ward',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Ward',
        related_name='users'
    )
    
    is_email_verified = models.BooleanField(default=False, verbose_name='Email Verified')
    email_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Email Verified At')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [models.Index(fields=['email']), models.Index(fields=['phone'])]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            base_username = self.email.split('@')[0][:30]
            if not User.objects.filter(username=base_username).exists():
                self.username = base_username
            else:
                self.username = f"{base_username}_{secrets.token_hex(3)}"
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @property
    def full_address(self) -> str:
        parts = [self.address, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))

    def verify_email(self) -> None:
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=['is_email_verified', 'email_verified_at', 'updated_at'])


class UserAddress(TimeStampedModel):
    """Shipping address for user."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', verbose_name='User')
    label = models.CharField(max_length=50, default='Home', verbose_name='Label')
    recipient_name = models.CharField(max_length=100, verbose_name='Recipient Name')
    phone = models.CharField(max_length=15, validators=[phone_validator], verbose_name='Phone Number')
    street = models.CharField(max_length=255, verbose_name='Street Address')
    ward = models.CharField(max_length=100, verbose_name='Ward')
    district = models.CharField(max_length=100, verbose_name='District')
    city = models.CharField(max_length=100, verbose_name='City/Province')
    province_id = models.IntegerField(verbose_name='GHN Province ID')
    district_id = models.IntegerField(verbose_name='GHN District ID')
    ward_code = models.CharField(max_length=20, verbose_name='GHN Ward Code')
    is_default = models.BooleanField(default=False, verbose_name='Default Address')

    class Meta:
        verbose_name = 'Shipping Address'
        verbose_name_plural = 'Shipping Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self) -> str:
        return f"{self.label} - {self.recipient_name}"

    def save(self, *args, **kwargs):
        if self.is_default:
            UserAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not UserAddress.objects.filter(user=self.user).exists():
            self.is_default = True
        super().save(*args, **kwargs)

    @property
    def full_address(self) -> str:
        parts = [self.street, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))


class SocialAccount(TimeStampedModel):
    """Linked social account for OAuth."""

    class Provider(models.TextChoices):
        GITHUB = 'github', 'GitHub'
        GOOGLE = 'google', 'Google'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts', verbose_name='User')
    provider = models.CharField(max_length=20, choices=Provider.choices, verbose_name='Provider')
    uid = models.CharField(max_length=255, verbose_name='Provider User ID')
    extra_data = models.JSONField(default=dict, blank=True, verbose_name='Extra Data')

    class Meta:
        verbose_name = 'Social Account'
        verbose_name_plural = 'Social Accounts'
        unique_together = ['provider', 'uid']

    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_provider_display()}"


class UserSession(TimeStampedModel):
    """Track active user sessions."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions', verbose_name='User')
    session_key = models.CharField(max_length=64, unique=True, db_index=True)
    refresh_token_hash = models.CharField(max_length=64, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-last_activity']
        indexes = [models.Index(fields=['user', 'is_active']), models.Index(fields=['session_key'])]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.device_name or self.device_type}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def terminate(self) -> None:
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class LoginHistory(TimeStampedModel):
    """Audit log for login attempts."""

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        BLOCKED = 'blocked', 'Blocked'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='login_history')
    email = models.EmailField(verbose_name='Login Email')
    status = models.CharField(max_length=20, choices=Status.choices, verbose_name='Status')
    fail_reason = models.CharField(max_length=30, blank=True, verbose_name='Failure Reason')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Login History'
        verbose_name_plural = 'Login History'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at']), models.Index(fields=['ip_address', '-created_at'])]

    def __str__(self) -> str:
        return f"{self.email} - {self.get_status_display()}"


class UserPreferences(TimeStampedModel):
    """User preferences and settings."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences', primary_key=True)
    email_notifications = models.BooleanField(default=True, verbose_name='Email Notifications')
    order_updates = models.BooleanField(default=True, verbose_name='Order Updates')
    promotional_emails = models.BooleanField(default=False, verbose_name='Promotional Emails')
    push_notifications = models.BooleanField(default=True, verbose_name='Push Notifications')
    sms_notifications = models.BooleanField(default=False, verbose_name='SMS Notifications')
    language = models.CharField(max_length=10, default='en', verbose_name='Language')
    currency = models.CharField(max_length=3, default='VND', verbose_name='Currency')
    two_factor_enabled = models.BooleanField(default=False, verbose_name='2FA Enabled')

    class Meta:
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'

    def __str__(self) -> str:
        return f"Preferences for {self.user.email}"
