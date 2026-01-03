"""
Users Notifications - Production-Ready Models.

Comprehensive notification system with:
- Notification: In-app notifications with read status
- NotificationTemplate: Reusable notification templates
- NotificationPreference: Per-user channel preferences
- DeviceToken: Push notification tokens
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.common.core.models import TimeStampedModel, UUIDModel


class NotificationType(models.TextChoices):
    """Notification type categories."""
    # Orders
    ORDER_PLACED = 'order_placed', 'Đơn hàng mới'
    ORDER_CONFIRMED = 'order_confirmed', 'Đơn hàng đã xác nhận'
    ORDER_SHIPPED = 'order_shipped', 'Đang giao hàng'
    ORDER_DELIVERED = 'order_delivered', 'Đã giao hàng'
    ORDER_CANCELLED = 'order_cancelled', 'Đơn hàng đã hủy'
    
    # Payments
    PAYMENT_SUCCESS = 'payment_success', 'Thanh toán thành công'
    PAYMENT_FAILED = 'payment_failed', 'Thanh toán thất bại'
    REFUND_PROCESSED = 'refund_processed', 'Hoàn tiền thành công'
    
    # Account
    WELCOME = 'welcome', 'Chào mừng'
    EMAIL_VERIFIED = 'email_verified', 'Email đã xác thực'
    PASSWORD_CHANGED = 'password_changed', 'Đổi mật khẩu'
    NEW_LOGIN = 'new_login', 'Đăng nhập mới'
    SECURITY_ALERT = 'security_alert', 'Cảnh báo bảo mật'
    
    # Marketing
    PROMOTION = 'promotion', 'Khuyến mãi'
    FLASH_SALE = 'flash_sale', 'Flash Sale'
    PRICE_DROP = 'price_drop', 'Giảm giá sản phẩm'
    BACK_IN_STOCK = 'back_in_stock', 'Có hàng trở lại'
    
    # Reviews
    REVIEW_REPLY = 'review_reply', 'Trả lời đánh giá'
    REVIEW_HELPFUL = 'review_helpful', 'Đánh giá hữu ích'
    
    # System
    SYSTEM = 'system', 'Thông báo hệ thống'
    ANNOUNCEMENT = 'announcement', 'Thông báo chung'


class NotificationChannel(models.TextChoices):
    """Notification delivery channels."""
    IN_APP = 'in_app', 'Trong ứng dụng'
    EMAIL = 'email', 'Email'
    PUSH = 'push', 'Push notification'
    SMS = 'sms', 'SMS'


class Notification(UUIDModel):
    """
    In-app notification for users.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Người dùng'
    )
    
    # Content
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
        verbose_name='Loại'
    )
    title = models.CharField(max_length=200, verbose_name='Tiêu đề')
    message = models.TextField(verbose_name='Nội dung')
    
    # Optional rich content
    image_url = models.URLField(blank=True, verbose_name='Hình ảnh')
    action_url = models.CharField(max_length=500, blank=True, verbose_name='Link hành động')
    action_text = models.CharField(max_length=50, blank=True, verbose_name='Text nút')
    
    # Metadata (for dynamic content)
    data = models.JSONField(default=dict, blank=True, verbose_name='Dữ liệu bổ sung')
    
    # Status
    is_read = models.BooleanField(default=False, db_index=True, verbose_name='Đã đọc')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Đọc lúc')
    
    # Delivery tracking
    channels_sent = models.JSONField(default=list, blank=True)  # ['email', 'push']
    
    # Priority
    priority = models.PositiveSmallIntegerField(default=1)  # 1=low, 2=medium, 3=high
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Thông báo'
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
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
    
    def mark_as_unread(self) -> None:
        """Mark notification as unread."""
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])


class NotificationTemplate(TimeStampedModel):
    """
    Reusable notification templates.
    """
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        unique=True,
        verbose_name='Loại'
    )
    
    # In-app template
    title_template = models.CharField(max_length=200, verbose_name='Template tiêu đề')
    message_template = models.TextField(verbose_name='Template nội dung')
    action_url_template = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=50, blank=True)
    
    # Email template
    email_subject_template = models.CharField(max_length=200, blank=True)
    email_template_name = models.CharField(max_length=100, blank=True)
    
    # Push notification
    push_title_template = models.CharField(max_length=100, blank=True)
    push_body_template = models.CharField(max_length=200, blank=True)
    
    # SMS
    sms_template = models.CharField(max_length=160, blank=True)
    
    # Defaults
    default_channels = models.JSONField(default=list)
    default_priority = models.PositiveSmallIntegerField(default=1)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Template thông báo'
        verbose_name_plural = 'Template thông báo'
    
    def __str__(self) -> str:
        return self.get_notification_type_display()
    
    def render(self, context: dict) -> dict:
        """Render template with context."""
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
    """
    User's notification preferences per type.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Người dùng'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        verbose_name='Loại'
    )
    
    # Channel preferences
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Cài đặt thông báo'
        verbose_name_plural = 'Cài đặt thông báo'
        unique_together = ['user', 'notification_type']
    
    def __str__(self) -> str:
        return f"{self.user.email}: {self.get_notification_type_display()}"
    
    def get_enabled_channels(self) -> list:
        """Get list of enabled channels."""
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
    """
    Push notification device tokens.
    """
    
    class Platform(models.TextChoices):
        IOS = 'ios', 'iOS'
        ANDROID = 'android', 'Android'
        WEB = 'web', 'Web'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        verbose_name='Người dùng'
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
        """Mark token as inactive."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])


class NotificationLog(TimeStampedModel):
    """
    Delivery log for notifications.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Đang chờ'
        SENT = 'sent', 'Đã gửi'
        FAILED = 'failed', 'Thất bại'
        DELIVERED = 'delivered', 'Đã nhận'
    
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='delivery_logs',
        verbose_name='Thông báo'
    )
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices,
        verbose_name='Kênh'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Trạng thái'
    )
    
    # Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    
    # Error info
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    
    # External IDs
    external_id = models.CharField(max_length=200, blank=True)
    
    class Meta:
        verbose_name = 'Log gửi thông báo'
        verbose_name_plural = 'Log gửi thông báo'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.notification}: {self.channel} - {self.status}"
    
    def mark_sent(self, external_id: str = ''):
        """Mark as sent."""
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.external_id = external_id
        self.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
    
    def mark_failed(self, error: str):
        """Mark as failed."""
        self.status = self.Status.FAILED
        self.error_message = error
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])
    
    def mark_delivered(self):
        """Mark as delivered."""
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'updated_at'])
