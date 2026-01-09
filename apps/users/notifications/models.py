import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import TimeStampedModel, UUIDModel


class NotificationType(models.TextChoices):
    ORDER_PLACED = 'order_placed', 'New Order'
    ORDER_CONFIRMED = 'order_confirmed', 'Order Confirmed'
    ORDER_SHIPPED = 'order_shipped', 'Shipping'
    ORDER_DELIVERED = 'order_delivered', 'Delivered'
    ORDER_CANCELLED = 'order_cancelled', 'Order Cancelled'
    PAYMENT_SUCCESS = 'payment_success', 'Payment Success'
    PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
    REFUND_PROCESSED = 'refund_processed', 'Refund Processed'
    WELCOME = 'welcome', 'Welcome'
    EMAIL_VERIFIED = 'email_verified', 'Email Verified'
    PASSWORD_CHANGED = 'password_changed', 'Password Changed'
    NEW_LOGIN = 'new_login', 'New Login'
    SECURITY_ALERT = 'security_alert', 'Security Alert'
    PROMOTION = 'promotion', 'Promotion'
    FLASH_SALE = 'flash_sale', 'Flash Sale'
    PRICE_DROP = 'price_drop', 'Price Drop'
    BACK_IN_STOCK = 'back_in_stock', 'Back In Stock'
    REVIEW_REPLY = 'review_reply', 'Review Reply'
    REVIEW_HELPFUL = 'review_helpful', 'Helpful Review'
    SYSTEM = 'system', 'System Notification'
    ANNOUNCEMENT = 'announcement', 'Announcement'


class NotificationChannel(models.TextChoices):
    IN_APP = 'in_app', 'In App'
    EMAIL = 'email', 'Email'
    PUSH = 'push', 'Push Notification'
    SMS = 'sms', 'SMS'


class Notification(UUIDModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='User'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
        verbose_name='Type'
    )
    title = models.CharField(max_length=200, verbose_name='Title')
    message = models.TextField(verbose_name='Message')
    image_url = models.URLField(blank=True, verbose_name='Image')
    action_url = models.CharField(max_length=500, blank=True, verbose_name='Action URL')
    action_text = models.CharField(max_length=50, blank=True, verbose_name='Button Text')
    data = models.JSONField(default=dict, blank=True, verbose_name='Extra Data')
    is_read = models.BooleanField(default=False, db_index=True, verbose_name='Read')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Read At')
    channels_sent = models.JSONField(default=list, blank=True)
    priority = models.PositiveSmallIntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', 'notification_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.user.email}: {self.title[:50]}"

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def mark_as_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def mark_as_unread(self) -> None:
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])


class NotificationTemplate(TimeStampedModel):
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        unique=True,
        verbose_name='Type'
    )
    title_template = models.CharField(max_length=200, verbose_name='Title Template')
    message_template = models.TextField(verbose_name='Message Template')
    action_url_template = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=50, blank=True)
    email_subject_template = models.CharField(max_length=200, blank=True)
    email_template_name = models.CharField(max_length=100, blank=True)
    push_title_template = models.CharField(max_length=100, blank=True)
    push_body_template = models.CharField(max_length=200, blank=True)
    sms_template = models.CharField(max_length=160, blank=True)
    default_channels = models.JSONField(default=list)
    default_priority = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'

    def __str__(self) -> str:
        return self.get_notification_type_display()

    def render(self, context: dict) -> dict:
        return {
            'title': self.title_template.format(**context),
            'message': self.message_template.format(**context),
            'action_url': self.action_url_template.format(**context) if self.action_url_template else '',
            'action_text': self.action_text,
            'email_subject': self.email_subject_template.format(**context) if self.email_subject_template else '',
            'push_title': self.push_title_template.format(**context) if self.push_title_template else '',
            'push_body': self.push_body_template.format(**context) if self.push_body_template else '',
            'sms': self.sms_template.format(**context) if self.sms_template else '',
        }


class NotificationPreference(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='User'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        verbose_name='Type'
    )
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
        unique_together = ['user', 'notification_type']

    def __str__(self) -> str:
        return f"{self.user.email}: {self.get_notification_type_display()}"

    def get_enabled_channels(self) -> list:
        channels = []
        if self.in_app_enabled:
            channels.append('in_app')
        if self.email_enabled:
            channels.append('email')
        if self.push_enabled:
            channels.append('push')
        if self.sms_enabled:
            channels.append('sms')
        return channels


class DeviceToken(TimeStampedModel):
    class Platform(models.TextChoices):
        IOS = 'ios', 'iOS'
        ANDROID = 'android', 'Android'
        WEB = 'web', 'Web'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        verbose_name='User'
    )
    token = models.CharField(max_length=500, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.user.email}: {self.platform} - {self.device_name or self.token[:20]}"

    def deactivate(self) -> None:
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class NotificationLog(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        DELIVERED = 'delivered', 'Delivered'

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='delivery_logs',
        verbose_name='Notification'
    )
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices,
        verbose_name='Channel'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    external_id = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.notification}: {self.channel} - {self.status}"

    def mark_sent(self, external_id: str = ''):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.external_id = external_id
        self.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.error_message = error
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])

    def mark_delivered(self):
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'updated_at'])
