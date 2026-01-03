"""
Commerce Orders - Production-Ready Models.

Order management models with:
- Order: Aggregate root with comprehensive state machine
- OrderItem: Immutable product snapshot
- OrderStatusHistory: Audit trail for status changes
- OrderNote: Internal admin notes
"""
import uuid
import time
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class Order(UUIDModel):
    """
    Order aggregate root.
    
    Represents a customer order with full state machine,
    shipping, payment tracking, and audit trail.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xác nhận'
        CONFIRMED = 'confirmed', 'Đã xác nhận'
        PROCESSING = 'processing', 'Đang xử lý'
        READY_TO_SHIP = 'ready_to_ship', 'Chờ giao hàng'
        SHIPPING = 'shipping', 'Đang giao hàng'
        DELIVERED = 'delivered', 'Đã giao hàng'
        COMPLETED = 'completed', 'Hoàn thành'
        CANCELLED = 'cancelled', 'Đã hủy'
        REFUNDED = 'refunded', 'Đã hoàn tiền'
        FAILED = 'failed', 'Thất bại'
    
    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Chưa thanh toán'
        PENDING = 'pending', 'Đang xử lý'
        PAID = 'paid', 'Đã thanh toán'
        FAILED = 'failed', 'Thanh toán thất bại'
        PARTIAL_REFUND = 'partial_refund', 'Hoàn một phần'
        REFUNDED = 'refunded', 'Đã hoàn tiền'
    
    class PaymentMethod(models.TextChoices):
        COD = 'cod', 'Thanh toán khi nhận hàng'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'MoMo'
    
    class Source(models.TextChoices):
        WEB = 'web', 'Website'
        MOBILE_APP = 'mobile', 'Ứng dụng mobile'
        ADMIN = 'admin', 'Admin tạo'
        API = 'api', 'API'
    
    # Core fields
    order_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Mã đơn hàng'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Khách hàng'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Trạng thái'
    )
    
    # Order source
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.WEB,
        verbose_name='Nguồn đơn'
    )
    
    # Shipping address (snapshot at order time)
    recipient_name = models.CharField(max_length=100, verbose_name='Tên người nhận')
    phone = models.CharField(max_length=15, db_index=True, verbose_name='Số điện thoại')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.CharField(max_length=255, verbose_name='Địa chỉ')
    ward = models.CharField(max_length=100, verbose_name='Phường/Xã')
    district = models.CharField(max_length=100, verbose_name='Quận/Huyện')
    city = models.CharField(max_length=100, verbose_name='Tỉnh/Thành phố')
    country = models.CharField(max_length=50, default='Vietnam', verbose_name='Quốc gia')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='Mã bưu điện')
    
    # GHN IDs for shipping
    district_id = models.IntegerField(verbose_name='Mã quận GHN')
    ward_code = models.CharField(max_length=20, verbose_name='Mã phường GHN')
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
        db_index=True,
        verbose_name='Phương thức thanh toán'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
        verbose_name='Trạng thái thanh toán'
    )
    
    # Amounts
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Tạm tính'
    )
    shipping_fee = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Phí vận chuyển'
    )
    insurance_fee = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Phí bảo hiểm'
    )
    discount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Giảm giá'
    )
    tax = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Thuế'
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Tổng cộng'
    )
    
    # Currency
    currency = models.CharField(max_length=3, default='VND', verbose_name='Đơn vị tiền')
    
    # Coupon
    coupon = models.ForeignKey(
        'marketing.Coupon',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders',
        verbose_name='Mã khuyến mãi'
    )
    coupon_code = models.CharField(max_length=50, blank=True, verbose_name='Mã giảm giá')
    coupon_discount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Giảm từ coupon'
    )
    
    # Tracking
    tracking_code = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name='Mã vận đơn'
    )
    shipping_provider = models.CharField(
        max_length=20, blank=True,
        verbose_name='Đơn vị vận chuyển'
    )
    
    # Notes
    customer_note = models.TextField(blank=True, verbose_name='Ghi chú khách hàng')
    admin_note = models.TextField(blank=True, verbose_name='Ghi chú nội bộ')
    
    # Priority/Tags
    is_priority = models.BooleanField(default=False, verbose_name='Đơn ưu tiên')
    is_gift = models.BooleanField(default=False, verbose_name='Đơn quà tặng')
    gift_message = models.TextField(blank=True, verbose_name='Lời nhắn quà tặng')
    
    # Timestamps
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian xác nhận')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian thanh toán')
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian giao cho vận chuyển')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian giao hàng')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian hoàn thành')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian hủy')
    
    # Cancellation/Failure
    cancel_reason = models.TextField(blank=True, verbose_name='Lý do hủy')
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cancelled_orders',
        verbose_name='Người hủy'
    )
    
    # Analytics
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP address')
    user_agent = models.TextField(blank=True, verbose_name='User agent')
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = 'Đơn hàng'
        verbose_name_plural = 'Đơn hàng'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['payment_status', '-created_at']),
            models.Index(fields=['payment_method', 'status']),
            models.Index(fields=['-created_at']),
        ]
        permissions = [
            ('can_view_all_orders', 'Can view all orders'),
            ('can_cancel_orders', 'Can cancel orders'),
            ('can_refund_orders', 'Can refund orders'),
            ('can_export_orders', 'Can export orders'),
        ]
    
    def __str__(self) -> str:
        return f"Đơn hàng #{self.order_number}"
    
    def save(self, *args, **kwargs):
        from django.db import IntegrityError, transaction
        
        if not self.order_number:
            # Retry up to 5 times if order number collision
            for attempt in range(5):
                try:
                    self.order_number = self._generate_order_number()
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError as e:
                    if 'order_number' in str(e).lower() and attempt < 4:
                        continue
                    raise
            raise ValueError("Không thể sinh mã đơn hàng duy nhất")
        else:
            super().save(*args, **kwargs)
    
    @staticmethod
    def _generate_order_number() -> str:
        """Generate unique order number with better entropy."""
        import secrets
        timestamp = str(int(time.time()))[-6:]  # 6 digits of timestamp
        random_part = secrets.token_hex(3).upper()  # 6 random hex chars
        return f"OWL{timestamp}{random_part}"
    
    # --- Computed Properties ---
    
    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))
    
    @property
    def item_count(self) -> int:
        """Total number of items in order."""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def unique_item_count(self) -> int:
        """Number of unique products."""
        return self.items.count()
    
    @property
    def can_cancel(self) -> bool:
        """Check if order can be cancelled."""
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]
    
    @property
    def can_refund(self) -> bool:
        """Check if order can be refunded."""
        return (
            self.status in [self.Status.DELIVERED, self.Status.COMPLETED] and
            self.payment_status == self.PaymentStatus.PAID
        )
    
    @property
    def is_paid(self) -> bool:
        """Check if order is paid."""
        return self.payment_status == self.PaymentStatus.PAID
    
    @property
    def is_cod(self) -> bool:
        """Check if payment method is COD."""
        return self.payment_method == self.PaymentMethod.COD
    
    @property
    def needs_payment(self) -> bool:
        """Check if order needs online payment."""
        return (
            not self.is_cod and
            self.payment_status in [self.PaymentStatus.UNPAID, self.PaymentStatus.FAILED]
        )
    
    @property
    def days_since_order(self) -> int:
        """Days since order was placed."""
        delta = timezone.now() - self.created_at
        return delta.days
    
    @property
    def processing_time_hours(self) -> float:
        """Hours from order to shipping."""
        if self.shipped_at:
            delta = self.shipped_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return 0
    
    @property
    def delivery_time_days(self) -> int:
        """Days from shipping to delivery."""
        if self.delivered_at and self.shipped_at:
            delta = self.delivered_at - self.shipped_at
            return delta.days
        return 0
    
    # --- State Transitions ---
    
    def confirm(self, admin_user=None) -> None:
        """Confirm order."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.PENDING:
            raise BusinessRuleViolation(
                message=f'Không thể xác nhận đơn hàng ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)
    
    def mark_processing(self, admin_user=None) -> None:
        """Mark as processing."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status not in [self.Status.PENDING, self.Status.CONFIRMED]:
            raise BusinessRuleViolation(
                message=f'Không thể chuyển sang xử lý ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.PROCESSING
        if not self.confirmed_at:
            self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)
    
    def mark_ready_to_ship(self, admin_user=None) -> None:
        """Mark as ready to ship."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status not in [self.Status.CONFIRMED, self.Status.PROCESSING]:
            raise BusinessRuleViolation(
                message=f'Không thể đánh dấu sẵn sàng giao ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.READY_TO_SHIP
        self.save(update_fields=['status', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)
    
    def mark_as_paid(self, transaction_id: str = '', admin_user=None) -> None:
        """Mark order as paid."""
        old_payment_status = self.payment_status
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        
        # Auto-confirm if pending
        if self.status == self.Status.PENDING:
            old_status = self.status
            self.status = self.Status.CONFIRMED
            self.confirmed_at = timezone.now()
            self.save(update_fields=[
                'payment_status', 'paid_at', 'status', 'confirmed_at', 'updated_at'
            ])
            self._log_status_change(old_status, self.status, admin_user, 
                                    f'Payment received: {transaction_id}')
        else:
            self.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
    
    def ship(self, tracking_code: str, provider: str = 'ghn', admin_user=None) -> None:
        """Mark order as shipped."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status not in [self.Status.CONFIRMED, self.Status.PROCESSING, self.Status.READY_TO_SHIP]:
            raise BusinessRuleViolation(
                message=f'Không thể giao hàng ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.SHIPPING
        self.tracking_code = tracking_code
        self.shipping_provider = provider
        self.shipped_at = timezone.now()
        self.save(update_fields=[
            'status', 'tracking_code', 'shipping_provider', 'shipped_at', 'updated_at'
        ])
        self._log_status_change(old_status, self.status, admin_user, 
                                f'Tracking: {tracking_code}')
    
    def deliver(self, admin_user=None) -> None:
        """Mark order as delivered."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.SHIPPING:
            raise BusinessRuleViolation(
                message=f'Không thể đánh dấu đã giao ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        
        # Mark COD as paid
        if self.is_cod:
            self.payment_status = self.PaymentStatus.PAID
            self.paid_at = timezone.now()
        
        self.save(update_fields=[
            'status', 'delivered_at', 'payment_status', 'paid_at', 'updated_at'
        ])
        self._log_status_change(old_status, self.status, admin_user)
    
    def complete(self, admin_user=None) -> None:
        """Mark order as completed (after return window)."""
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.DELIVERED:
            raise BusinessRuleViolation(
                message=f'Không thể hoàn thành đơn ở trạng thái {self.get_status_display()}'
            )
        
        old_status = self.status
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)
    
    def cancel(self, reason: str = '', cancelled_by=None) -> bool:
        """Cancel order and restore stock."""
        if not self.can_cancel:
            return False
        
        old_status = self.status
        
        # Restore stock
        for item in self.items.select_related('product').all():
            if item.product and hasattr(item.product, 'stock'):
                item.product.stock.release(item.quantity, self.order_number)
        
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason
        self.cancelled_by = cancelled_by
        self.save(update_fields=[
            'status', 'cancelled_at', 'cancel_reason', 'cancelled_by', 'updated_at'
        ])
        self._log_status_change(old_status, self.status, cancelled_by, reason)
        
        return True
    
    def mark_failed(self, reason: str = '', admin_user=None) -> None:
        """Mark order as failed."""
        old_status = self.status
        self.status = self.Status.FAILED
        self.cancel_reason = reason
        self.save(update_fields=['status', 'cancel_reason', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user, reason)
    
    def refund(self, admin_user=None) -> None:
        """Mark order as refunded."""
        old_status = self.status
        self.status = self.Status.REFUNDED
        self.payment_status = self.PaymentStatus.REFUNDED
        self.save(update_fields=['status', 'payment_status', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)
    
    def _log_status_change(
        self,
        old_status: str,
        new_status: str,
        changed_by=None,
        notes: str = ''
    ) -> None:
        """Create audit log for status change."""
        OrderStatusHistory.objects.create(
            order=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            notes=notes
        )


class OrderItem(TimeStampedModel):
    """
    Order line item (immutable snapshot).
    
    Stores product information at time of order.
    """
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Đơn hàng'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items',
        verbose_name='Sản phẩm'
    )
    
    # Snapshot at order time
    product_name = models.CharField(max_length=255, verbose_name='Tên sản phẩm')
    product_sku = models.CharField(max_length=50, blank=True, verbose_name='SKU')
    product_image = models.URLField(blank=True, max_length=500, verbose_name='Hình ảnh')
    product_attributes = models.JSONField(default=dict, blank=True, verbose_name='Thuộc tính')
    
    quantity = models.PositiveIntegerField(verbose_name='Số lượng')
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Đơn giá'
    )
    original_price = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name='Giá gốc'
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Giảm giá'
    )
    
    # For returns
    returned_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Số lượng đã trả'
    )
    
    class Meta:
        verbose_name = 'Sản phẩm trong đơn'
        verbose_name_plural = 'Sản phẩm trong đơn'
    
    def __str__(self) -> str:
        return f"{self.quantity}x {self.product_name}"
    
    @property
    def subtotal(self) -> Decimal:
        """Line item total."""
        return self.unit_price * self.quantity
    
    @property
    def total_discount(self) -> Decimal:
        """Total discount for line."""
        return self.discount_amount * self.quantity
    
    @property
    def is_on_sale(self) -> bool:
        """Check if item was on sale."""
        return self.original_price and self.original_price > self.unit_price
    
    @property
    def returnable_quantity(self) -> int:
        """Quantity that can still be returned."""
        return self.quantity - self.returned_quantity


class OrderStatusHistory(TimeStampedModel):
    """
    Audit trail for order status changes.
    """
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Đơn hàng'
    )
    old_status = models.CharField(
        max_length=20,
        choices=Order.Status.choices,
        verbose_name='Trạng thái cũ'
    )
    new_status = models.CharField(
        max_length=20,
        choices=Order.Status.choices,
        verbose_name='Trạng thái mới'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Người thay đổi'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    class Meta:
        verbose_name = 'Lịch sử trạng thái'
        verbose_name_plural = 'Lịch sử trạng thái'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.old_status} → {self.new_status}"


class OrderNote(TimeStampedModel):
    """
    Internal notes for an order.
    """
    
    class NoteType(models.TextChoices):
        GENERAL = 'general', 'Chung'
        PAYMENT = 'payment', 'Thanh toán'
        SHIPPING = 'shipping', 'Vận chuyển'
        CUSTOMER = 'customer', 'Khách hàng'
        ISSUE = 'issue', 'Vấn đề'
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name='Đơn hàng'
    )
    note_type = models.CharField(
        max_length=20,
        choices=NoteType.choices,
        default=NoteType.GENERAL,
        verbose_name='Loại ghi chú'
    )
    content = models.TextField(verbose_name='Nội dung')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Người tạo'
    )
    is_private = models.BooleanField(
        default=True,
        verbose_name='Chỉ admin xem'
    )
    
    class Meta:
        verbose_name = 'Ghi chú đơn hàng'
        verbose_name_plural = 'Ghi chú đơn hàng'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"Note for {self.order.order_number}"
