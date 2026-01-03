"""
Commerce Returns - Production-Ready Models.

Return/refund request models with:
- ReturnRequest: Main aggregate root
- ReturnItem: Individual items being returned
- ReturnImage: Evidence/photos for return requests
- ReturnStatusHistory: Audit trail for status changes
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel
from apps.commerce.orders.models import Order, OrderItem


class ReturnRequest(UUIDModel):
    """
    Return/exchange request aggregate root.
    
    Represents a customer's request to return items from an order.
    Supports partial returns (individual items) and full order returns.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ xử lý'
        REVIEWING = 'reviewing', 'Đang xem xét'
        APPROVED = 'approved', 'Đã duyệt'
        REJECTED = 'rejected', 'Từ chối'
        AWAITING_RETURN = 'awaiting_return', 'Chờ nhận hàng'
        RECEIVED = 'received', 'Đã nhận hàng'
        PROCESSING_REFUND = 'processing_refund', 'Đang hoàn tiền'
        COMPLETED = 'completed', 'Hoàn tất'
        CANCELLED = 'cancelled', 'Đã hủy'
    
    class Reason(models.TextChoices):
        DEFECTIVE = 'defective', 'Hàng lỗi/hư hỏng'
        WRONG_ITEM = 'wrong_item', 'Giao sai hàng'
        NOT_AS_DESCRIBED = 'not_as_described', 'Không đúng mô tả'
        MISSING_PARTS = 'missing_parts', 'Thiếu phụ kiện/linh kiện'
        SIZE_FIT = 'size_fit', 'Không vừa kích thước'
        CHANGED_MIND = 'changed_mind', 'Đổi ý'
        QUALITY = 'quality', 'Chất lượng không đạt'
        DAMAGED_SHIPPING = 'damaged_shipping', 'Hư hỏng khi vận chuyển'
        OTHER = 'other', 'Lý do khác'
    
    class RefundMethod(models.TextChoices):
        ORIGINAL = 'original', 'Hoàn về phương thức gốc'
        BANK_TRANSFER = 'bank_transfer', 'Chuyển khoản ngân hàng'
        WALLET = 'wallet', 'Ví điện tử'
        STORE_CREDIT = 'store_credit', 'Điểm thưởng/Credit'
    
    # Core relationships
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='return_requests',
        verbose_name='Đơn hàng'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='return_requests',
        verbose_name='Khách hàng'
    )
    
    # Request number for tracking
    request_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Mã yêu cầu'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Trạng thái'
    )
    
    # Reason
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        verbose_name='Lý do'
    )
    description = models.TextField(
        verbose_name='Mô tả chi tiết',
        help_text='Mô tả chi tiết về vấn đề với sản phẩm'
    )
    
    # Refund info
    refund_method = models.CharField(
        max_length=20,
        choices=RefundMethod.choices,
        default=RefundMethod.ORIGINAL,
        verbose_name='Phương thức hoàn tiền'
    )
    requested_refund = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Số tiền yêu cầu hoàn'
    )
    approved_refund = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Số tiền được duyệt'
    )
    
    # Bank info (if refund method is bank transfer)
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='Ngân hàng')
    bank_account_number = models.CharField(max_length=30, blank=True, verbose_name='Số tài khoản')
    bank_account_name = models.CharField(max_length=100, blank=True, verbose_name='Tên chủ tài khoản')
    
    # Return shipping
    return_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Mã vận đơn trả hàng'
    )
    return_carrier = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị vận chuyển')
    
    # Admin response
    admin_notes = models.TextField(blank=True, verbose_name='Ghi chú admin')
    rejection_reason = models.TextField(blank=True, verbose_name='Lý do từ chối')
    
    # Processing info
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_returns',
        verbose_name='Người xử lý'
    )
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian xử lý')
    
    # Quality check
    quality_check_passed = models.BooleanField(null=True, verbose_name='Kiểm tra chất lượng')
    quality_check_notes = models.TextField(blank=True, verbose_name='Ghi chú kiểm tra')
    
    # Timestamps
    received_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian nhận hàng')
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian hoàn tiền')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian hoàn tất')
    
    # Refund reference
    refund = models.ForeignKey(
        'billing.Refund',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='return_requests',
        verbose_name='Hoàn tiền'
    )
    
    class Meta:
        verbose_name = 'Yêu cầu hoàn trả'
        verbose_name_plural = 'Yêu cầu hoàn trả'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['order', 'status']),
        ]
        permissions = [
            ('can_approve_returns', 'Can approve return requests'),
            ('can_process_refunds', 'Can process refunds for returns'),
        ]
    
    def __str__(self) -> str:
        return f"Return {self.request_number} - {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self._generate_request_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def _generate_request_number() -> str:
        """Generate unique return request number."""
        import time
        timestamp = str(int(time.time()))[-6:]
        unique_id = str(uuid.uuid4().int)[:4]
        return f"RET{timestamp}{unique_id}"
    
    # --- Computed Properties ---
    
    @property
    def total_items(self) -> int:
        """Total number of items being returned."""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_partial_return(self) -> bool:
        """Check if this is a partial return."""
        order_items = self.order.items.count()
        return self.items.count() < order_items
    
    @property
    def can_cancel(self) -> bool:
        """Check if request can be cancelled by user."""
        return self.status in [self.Status.PENDING, self.Status.REVIEWING]
    
    @property
    def can_approve(self) -> bool:
        """Check if request can be approved."""
        return self.status in [self.Status.PENDING, self.Status.REVIEWING]
    
    @property
    def can_receive(self) -> bool:
        """Check if items can be marked as received."""
        return self.status in [self.Status.APPROVED, self.Status.AWAITING_RETURN]
    
    @property
    def days_since_delivery(self) -> int:
        """Days since order was delivered."""
        if self.order.delivered_at:
            delta = timezone.now() - self.order.delivered_at
            return delta.days
        return 0
    
    @property
    def is_within_return_window(self) -> bool:
        """Check if still within return window (default 7 days)."""
        return self.days_since_delivery <= 7
    
    # --- State Transitions ---
    
    def start_review(self, admin_user) -> None:
        """Move to reviewing status."""
        if self.status != self.Status.PENDING:
            return
        
        self.status = self.Status.REVIEWING
        self.processed_by = admin_user
        self.save(update_fields=['status', 'processed_by', 'updated_at'])
        self._log_status_change(self.Status.REVIEWING, admin_user)
    
    def approve(self, admin_user, approved_refund: Decimal, notes: str = '') -> None:
        """Approve return request."""
        if not self.can_approve:
            return
        
        self.status = self.Status.APPROVED
        self.approved_refund = approved_refund
        self.admin_notes = notes
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=[
            'status', 'approved_refund', 'admin_notes',
            'processed_by', 'processed_at', 'updated_at'
        ])
        self._log_status_change(self.Status.APPROVED, admin_user, notes)
    
    def reject(self, admin_user, reason: str) -> None:
        """Reject return request."""
        if not self.can_approve:
            return
        
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.approved_refund = 0
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=[
            'status', 'rejection_reason', 'approved_refund',
            'processed_by', 'processed_at', 'updated_at'
        ])
        self._log_status_change(self.Status.REJECTED, admin_user, reason)
    
    def mark_awaiting_return(self) -> None:
        """Mark as awaiting return shipment."""
        if self.status != self.Status.APPROVED:
            return
        
        self.status = self.Status.AWAITING_RETURN
        self.save(update_fields=['status', 'updated_at'])
        self._log_status_change(self.Status.AWAITING_RETURN)
    
    def receive_items(self, admin_user, quality_passed: bool, notes: str = '') -> None:
        """Mark items as received and inspected."""
        if not self.can_receive:
            return
        
        self.status = self.Status.RECEIVED
        self.quality_check_passed = quality_passed
        self.quality_check_notes = notes
        self.received_at = timezone.now()
        self.save(update_fields=[
            'status', 'quality_check_passed', 'quality_check_notes',
            'received_at', 'updated_at'
        ])
        self._log_status_change(self.Status.RECEIVED, admin_user, notes)
        
        # Restore stock if quality passed
        if quality_passed:
            self._restore_stock()
    
    def process_refund(self, refund) -> None:
        """Link refund and update status."""
        self.refund = refund
        self.status = self.Status.PROCESSING_REFUND
        self.refunded_at = timezone.now()
        self.save(update_fields=['refund', 'status', 'refunded_at', 'updated_at'])
        self._log_status_change(self.Status.PROCESSING_REFUND)
    
    def complete(self, admin_user=None) -> None:
        """Mark return as completed."""
        if self.status not in [self.Status.RECEIVED, self.Status.PROCESSING_REFUND]:
            return
        
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._log_status_change(self.Status.COMPLETED, admin_user)
    
    def cancel(self, user=None, reason: str = '') -> None:
        """Cancel return request."""
        if not self.can_cancel:
            return
        
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
        self._log_status_change(self.Status.CANCELLED, user, reason)
    
    # --- Internal Methods ---
    
    def _log_status_change(self, new_status: str, user=None, notes: str = '') -> None:
        """Create audit log entry."""
        ReturnStatusHistory.objects.create(
            return_request=self,
            status=new_status,
            changed_by=user,
            notes=notes
        )
    
    def _restore_stock(self) -> None:
        """Restore stock for returned items."""
        for item in self.items.all():
            if item.order_item.product and hasattr(item.order_item.product, 'stock'):
                item.order_item.product.stock.process_return(
                    item.quantity,
                    self.request_number
                )


class ReturnItem(TimeStampedModel):
    """
    Individual item in a return request.
    
    Allows partial returns where only some items/quantities are returned.
    """
    
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Yêu cầu hoàn trả'
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name='return_items',
        verbose_name='Sản phẩm đơn hàng'
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name='Số lượng trả'
    )
    
    # Item-specific reason (can differ from main request reason)
    reason = models.CharField(
        max_length=20,
        choices=ReturnRequest.Reason.choices,
        blank=True,
        verbose_name='Lý do cụ thể'
    )
    condition = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Tình trạng sản phẩm'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    # After inspection
    accepted_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Số lượng chấp nhận'
    )
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Số tiền hoàn cho item'
    )
    
    class Meta:
        verbose_name = 'Sản phẩm hoàn trả'
        verbose_name_plural = 'Sản phẩm hoàn trả'
        unique_together = ['return_request', 'order_item']
    
    def __str__(self) -> str:
        return f"{self.quantity}x {self.order_item.product_name}"
    
    @property
    def unit_price(self) -> Decimal:
        """Unit price from original order."""
        return self.order_item.unit_price
    
    @property
    def subtotal(self) -> Decimal:
        """Total value of items being returned."""
        return self.unit_price * self.quantity
    
    def clean(self):
        """Validate return quantity."""
        from django.core.exceptions import ValidationError
        
        if self.quantity > self.order_item.quantity:
            raise ValidationError({
                'quantity': f'Không thể trả nhiều hơn số lượng đã mua ({self.order_item.quantity})'
            })
        
        # Check if already returned
        existing_returns = ReturnItem.objects.filter(
            order_item=self.order_item,
            return_request__status__in=[
                ReturnRequest.Status.APPROVED,
                ReturnRequest.Status.RECEIVED,
                ReturnRequest.Status.COMPLETED
            ]
        ).exclude(pk=self.pk).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        if existing_returns + self.quantity > self.order_item.quantity:
            raise ValidationError({
                'quantity': f'Đã có {existing_returns} sản phẩm được duyệt hoàn trả'
            })


class ReturnImage(TimeStampedModel):
    """
    Evidence images for return request.
    
    Customers can upload photos showing product issues.
    """
    
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Yêu cầu hoàn trả'
    )
    image = models.ImageField(
        upload_to='returns/%Y/%m/',
        verbose_name='Hình ảnh'
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Chú thích'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Người tải lên'
    )
    
    class Meta:
        verbose_name = 'Hình ảnh hoàn trả'
        verbose_name_plural = 'Hình ảnh hoàn trả'
        ordering = ['created_at']
    
    def __str__(self) -> str:
        return f"Image for {self.return_request.request_number}"


class ReturnStatusHistory(TimeStampedModel):
    """
    Audit trail for return status changes.
    """
    
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Yêu cầu hoàn trả'
    )
    status = models.CharField(
        max_length=20,
        choices=ReturnRequest.Status.choices,
        verbose_name='Trạng thái'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Người thay đổi'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    class Meta:
        verbose_name = 'Lịch sử trạng thái'
        verbose_name_plural = 'Lịch sử trạng thái'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.return_request.request_number}: {self.status}"
