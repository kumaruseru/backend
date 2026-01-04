"""
Commerce Billing - Production-Ready Models.

Payment and billing models with:
- Payment: Transaction tracking with retry support
- Refund: Full and partial refund support  
- PaymentLog: Audit trail for all payment events
- PaymentMethod: Saved payment methods (cards, wallets)
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class Payment(UUIDModel):
    """
    Payment aggregate root.
    
    Tracks payment attempts for orders with:
    - Multiple retry support
    - Provider transaction tracking
    - Webhook data storage
    - Expiration handling
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Đang chờ'
        PROCESSING = 'processing', 'Đang xử lý'
        AWAITING_CAPTURE = 'awaiting_capture', 'Chờ capture'
        COMPLETED = 'completed', 'Hoàn thành'
        FAILED = 'failed', 'Thất bại'
        CANCELLED = 'cancelled', 'Đã hủy'
        EXPIRED = 'expired', 'Hết hạn'
        PARTIAL_REFUNDED = 'partial_refund', 'Hoàn một phần'
        REFUNDED = 'refunded', 'Đã hoàn tiền'
    
    class Method(models.TextChoices):
        COD = 'cod', 'Thanh toán khi nhận hàng'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'Ví MoMo'
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Đơn hàng'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Người dùng'
    )
    
    # Payment details
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        db_index=True,
        verbose_name='Phương thức'
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Số tiền'
    )
    currency = models.CharField(max_length=3, default='VND', verbose_name='Đơn vị tiền')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Trạng thái'
    )
    
    # Provider information
    transaction_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        verbose_name='Mã giao dịch gateway'
    )
    provider_transaction_id = models.CharField(
        max_length=255, blank=True,
        verbose_name='Mã giao dịch provider'
    )
    payment_url = models.TextField(blank=True, verbose_name='URL thanh toán')
    qr_code_url = models.TextField(blank=True, verbose_name='QR Code URL')
    
    # Provider metadata
    provider_data = models.JSONField(default=dict, blank=True, verbose_name='Dữ liệu provider')
    webhook_data = models.JSONField(default=dict, blank=True, verbose_name='Dữ liệu webhook')
    
    # Failure tracking
    failure_reason = models.TextField(blank=True, verbose_name='Lý do thất bại')
    failure_code = models.CharField(max_length=50, blank=True, verbose_name='Mã lỗi')
    retry_count = models.PositiveSmallIntegerField(default=0, verbose_name='Số lần thử lại')
    max_retries = models.PositiveSmallIntegerField(default=3, verbose_name='Số lần thử tối đa')
    
    # Timing
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Hết hạn lúc')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Thanh toán lúc')
    captured_at = models.DateTimeField(null=True, blank=True, verbose_name='Capture lúc')
    
    # Refund tracking
    refunded_amount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Số tiền đã hoàn'
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    device_info = models.JSONField(default=dict, blank=True, verbose_name='Device info')
    
    class Meta:
        verbose_name = 'Thanh toán'
        verbose_name_plural = 'Thanh toán'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['method', 'status']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self) -> str:
        return f"Payment {self.id} - {self.order.order_number}"
    
    # --- Computed Properties ---
    
    @property
    def is_completed(self) -> bool:
        """Check if payment is completed."""
        return self.status == self.Status.COMPLETED
    
    @property
    def is_pending(self) -> bool:
        """Check if payment is pending."""
        return self.status == self.Status.PENDING
    
    @property
    def is_failed(self) -> bool:
        """Check if payment failed."""
        return self.status in [self.Status.FAILED, self.Status.CANCELLED, self.Status.EXPIRED]
    
    @property
    def is_expired(self) -> bool:
        """Check if payment is expired."""
        if self.status == self.Status.EXPIRED:
            return True
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    @property
    def can_retry(self) -> bool:
        """Check if payment can be retried."""
        return (
            self.status in [self.Status.FAILED, self.Status.EXPIRED] and
            self.retry_count < self.max_retries
        )
    
    @property
    def can_refund(self) -> bool:
        """Check if payment can be refunded."""
        return self.status == self.Status.COMPLETED and self.refundable_amount > 0
    
    @property
    def refundable_amount(self) -> Decimal:
        """Amount that can still be refunded."""
        return self.amount - self.refunded_amount
    
    @property
    def is_fully_refunded(self) -> bool:
        """Check if fully refunded."""
        return self.refunded_amount >= self.amount
    
    # --- State Transitions ---
    
    def mark_processing(self, transaction_id: str = '') -> None:
        """Mark payment as processing."""
        old_status = self.status
        self.status = self.Status.PROCESSING
        if transaction_id:
            self.transaction_id = transaction_id
        self.save(update_fields=['status', 'transaction_id', 'updated_at'])
        self._log_event('processing', old_status)
    
    def mark_completed(self, transaction_id: str = None, provider_data: dict = None) -> bool:
        """Mark payment as completed."""
        if self.status == self.Status.COMPLETED:
            return False
        
        old_status = self.status
        self.status = self.Status.COMPLETED
        self.paid_at = timezone.now()
        self.captured_at = timezone.now()
        
        if transaction_id:
            self.transaction_id = transaction_id
        if provider_data:
            self.provider_data = {**self.provider_data, **provider_data}
        
        self.save(update_fields=[
            'status', 'paid_at', 'captured_at', 'transaction_id',
            'provider_data', 'updated_at'
        ])
        
        # Emit signal for Order to handle (DECOUPLED)
        from .signals import payment_completed
        payment_completed.send(sender=self.__class__, payment=self)
        
        self._log_event('completed', old_status)
        
        return True
    
    def mark_failed(self, reason: str = '', code: str = '') -> None:
        """Mark payment as failed."""
        old_status = self.status
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.failure_code = code
        self.save(update_fields=['status', 'failure_reason', 'failure_code', 'updated_at'])
        self._log_event('failed', old_status, notes=reason)
    
    def mark_cancelled(self, reason: str = '') -> None:
        """Mark payment as cancelled."""
        old_status = self.status
        self.status = self.Status.CANCELLED
        self.failure_reason = reason
        self.save(update_fields=['status', 'failure_reason', 'updated_at'])
        self._log_event('cancelled', old_status, notes=reason)
    
    def mark_expired(self) -> None:
        """Mark payment as expired."""
        if self.status in [self.Status.COMPLETED, self.Status.REFUNDED]:
            return
        
        old_status = self.status
        self.status = self.Status.EXPIRED
        self.save(update_fields=['status', 'updated_at'])
        self._log_event('expired', old_status)
    
    def increment_retry(self) -> bool:
        """Increment retry count."""
        if not self.can_retry:
            return False
        
        self.retry_count += 1
        self.status = self.Status.PENDING
        self.save(update_fields=['retry_count', 'status', 'updated_at'])
        self._log_event('retry', 'failed', notes=f'Retry #{self.retry_count}')
        
        return True
    
    def add_refund(self, amount: Decimal) -> None:
        """Add refund amount."""
        self.refunded_amount += amount
        
        if self.is_fully_refunded:
            self.status = self.Status.REFUNDED
        else:
            self.status = self.Status.PARTIAL_REFUNDED
        
        self.save(update_fields=['refunded_amount', 'status', 'updated_at'])
    
    def _log_event(self, event: str, old_status: str, notes: str = '') -> None:
        """Create payment log entry."""
        PaymentLog.objects.create(
            payment=self,
            event=event,
            old_status=old_status,
            new_status=self.status,
            notes=notes
        )


class Refund(UUIDModel):
    """
    Refund entity.
    
    Supports full and partial refunds with provider tracking.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Đang chờ'
        PROCESSING = 'processing', 'Đang xử lý'
        COMPLETED = 'completed', 'Hoàn thành'
        FAILED = 'failed', 'Thất bại'
    
    class Type(models.TextChoices):
        FULL = 'full', 'Hoàn toàn bộ'
        PARTIAL = 'partial', 'Hoàn một phần'
    
    class Reason(models.TextChoices):
        CUSTOMER_REQUEST = 'customer_request', 'Khách yêu cầu'
        DUPLICATE = 'duplicate', 'Thanh toán trùng'
        FRAUDULENT = 'fraudulent', 'Gian lận'
        ORDER_CANCELLED = 'order_cancelled', 'Đơn hàng bị hủy'
        RETURN = 'return', 'Hoàn trả hàng'
        OTHER = 'other', 'Khác'
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name='Thanh toán'
    )
    
    refund_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.FULL,
        verbose_name='Loại hoàn'
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Số tiền hoàn'
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        default=Reason.OTHER,
        verbose_name='Lý do'
    )
    reason_detail = models.TextField(blank=True, verbose_name='Chi tiết lý do')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    
    # Provider tracking
    refund_id = models.CharField(
        max_length=255, blank=True,
        verbose_name='Mã hoàn tiền gateway'
    )
    provider_refund_id = models.CharField(
        max_length=255, blank=True,
        verbose_name='Mã hoàn tiền provider'
    )
    provider_data = models.JSONField(default=dict, blank=True)
    
    # Failure
    failure_reason = models.TextField(blank=True)
    
    # Processing
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='processed_refunds',
        verbose_name='Người xử lý'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Hoàn tiền'
        verbose_name_plural = 'Hoàn tiền'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"Refund {self.id} - {self.payment.order.order_number}"
    
    @property
    def is_completed(self) -> bool:
        return self.status == self.Status.COMPLETED
    
    def mark_completed(self, refund_id: str = '', provider_data: dict = None) -> None:
        """Mark refund as completed."""
        self.status = self.Status.COMPLETED
        self.processed_at = timezone.now()
        if refund_id:
            self.refund_id = refund_id
        if provider_data:
            self.provider_data = {**self.provider_data, **provider_data}
        
        self.save(update_fields=[
            'status', 'processed_at', 'refund_id', 'provider_data', 'updated_at'
        ])
        
        # Update payment refunded amount
        self.payment.add_refund(self.amount)
    
    def mark_failed(self, reason: str = '') -> None:
        """Mark refund as failed."""
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.save(update_fields=['status', 'failure_reason', 'updated_at'])


class PaymentLog(TimeStampedModel):
    """
    Audit trail for payment events.
    """
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Thanh toán'
    )
    event = models.CharField(max_length=50, verbose_name='Sự kiện')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Log thanh toán'
        verbose_name_plural = 'Log thanh toán'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.payment_id}: {self.event}"


class PaymentMethod(UUIDModel):
    """
    Saved payment method (card, wallet).
    
    For recurring payments and quick checkout.
    """
    
    class Type(models.TextChoices):
        CARD = 'card', 'Thẻ tín dụng/ghi nợ'
        BANK_ACCOUNT = 'bank', 'Tài khoản ngân hàng'
        WALLET = 'wallet', 'Ví điện tử'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods',
        verbose_name='Người dùng'
    )
    
    method_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name='Loại'
    )
    provider = models.CharField(
        max_length=20,
        choices=Payment.Method.choices,
        verbose_name='Provider'
    )
    
    # Display info (masked/safe data only)
    display_name = models.CharField(max_length=100, verbose_name='Tên hiển thị')
    last_four = models.CharField(max_length=4, blank=True, verbose_name='4 số cuối')
    brand = models.CharField(max_length=30, blank=True, verbose_name='Thương hiệu')  # visa, mastercard
    
    # Provider token (for charging)
    token = models.CharField(max_length=255, verbose_name='Token')
    
    # Metadata
    is_default = models.BooleanField(default=False, verbose_name='Mặc định')
    is_active = models.BooleanField(default=True, verbose_name='Hoạt động')
    expires_at = models.DateField(null=True, blank=True, verbose_name='Hết hạn')
    
    # Billing address
    billing_name = models.CharField(max_length=100, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name = 'Phương thức thanh toán'
        verbose_name_plural = 'Phương thức thanh toán'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self) -> str:
        return f"{self.display_name} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per user
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user, is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)
