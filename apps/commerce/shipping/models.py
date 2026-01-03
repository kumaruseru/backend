"""
Commerce Shipping - Production-Ready Models.

Shipment tracking models with:
- Shipment: Main aggregate root with comprehensive status tracking
- ShipmentEvent: Detailed tracking event log
- ShipmentStatusHistory: Audit trail for manual status changes
- DeliveryAttempt: Failed delivery attempt tracking
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class Shipment(UUIDModel):
    """
    Shipment aggregate root.
    
    Tracks delivery status for orders with detailed
    event logging and COD handling.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ lấy hàng'
        PICKING = 'picking', 'Đang lấy hàng'
        PICKED_UP = 'picked_up', 'Đã lấy hàng'
        IN_TRANSIT = 'in_transit', 'Đang vận chuyển'
        SORTING = 'sorting', 'Đang phân loại'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Đang giao'
        DELIVERED = 'delivered', 'Đã giao'
        FAILED = 'failed', 'Giao thất bại'
        WAITING_RETURN = 'waiting_return', 'Chờ trả hàng'
        RETURNING = 'returning', 'Đang trả hàng'
        RETURNED = 'returned', 'Đã trả hàng'
        CANCELLED = 'cancelled', 'Đã hủy'
        EXCEPTION = 'exception', 'Ngoại lệ'
    
    class Provider(models.TextChoices):
        GHN = 'ghn', 'Giao Hàng Nhanh'
        GHTK = 'ghtk', 'Giao Hàng Tiết Kiệm'
        VIETTEL_POST = 'vtp', 'Viettel Post'
        VNPOST = 'vnpost', 'VNPost'
        JNT = 'jnt', 'J&T Express'
        NINJA_VAN = 'ninjavan', 'Ninja Van'
        BEST = 'best', 'BEST Express'
        MANUAL = 'manual', 'Tự giao'
    
    # Core relation
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='shipment',
        verbose_name='Đơn hàng'
    )
    
    # Provider info
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.GHN,
        db_index=True,
        verbose_name='Nhà vận chuyển'
    )
    tracking_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Mã vận đơn'
    )
    provider_order_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Mã đơn provider'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Trạng thái'
    )
    provider_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Trạng thái gốc từ provider'
    )
    
    # Shipping details
    weight = models.PositiveIntegerField(
        default=500,
        verbose_name='Trọng lượng (g)',
        help_text='Trọng lượng thực tế, đơn vị gram'
    )
    dimensions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Kích thước',
        help_text='{"length": cm, "width": cm, "height": cm}'
    )
    
    # Fees
    shipping_fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Phí vận chuyển'
    )
    insurance_fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Phí bảo hiểm'
    )
    cod_fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Phí COD'
    )
    total_fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Tổng phí'
    )
    
    # COD
    cod_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Tiền thu hộ'
    )
    cod_collected = models.BooleanField(
        default=False,
        verbose_name='Đã thu COD'
    )
    cod_transferred = models.BooleanField(
        default=False,
        verbose_name='Đã chuyển COD về shop'
    )
    cod_transfer_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Ngày chuyển COD'
    )
    
    # Provider response data
    provider_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Dữ liệu từ provider'
    )
    
    # Service type
    service_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Mã dịch vụ'
    )
    service_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Loại dịch vụ'
    )
    
    # Delivery info
    expected_delivery = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Dự kiến giao'
    )
    delivery_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name='Số lần giao'
    )
    max_delivery_attempts = models.PositiveIntegerField(
        default=3,
        verbose_name='Số lần giao tối đa'
    )
    
    # Special instructions
    required_note = models.CharField(
        max_length=50,
        default='CHOTHUHANG',
        verbose_name='Yêu cầu khi giao',
        help_text='CHOTHUHANG, CHOXEMHANGKHONGTHU, KHONGCHOXEMHANG'
    )
    note = models.TextField(
        blank=True,
        verbose_name='Ghi chú giao hàng'
    )
    
    # Timestamps
    picked_up_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời gian lấy hàng'
    )
    delivered_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời gian giao hàng'
    )
    returned_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời gian trả hàng'
    )
    cancelled_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời gian hủy'
    )
    
    # Tracking
    last_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Vị trí cuối'
    )
    last_status_update = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Cập nhật cuối từ provider'
    )
    
    # Reason for issues
    fail_reason = models.TextField(
        blank=True,
        verbose_name='Lý do giao thất bại'
    )
    cancel_reason = models.TextField(
        blank=True,
        verbose_name='Lý do hủy'
    )
    
    class Meta:
        verbose_name = 'Vận chuyển'
        verbose_name_plural = 'Vận chuyển'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['cod_amount', 'cod_collected']),
        ]
    
    def __str__(self) -> str:
        return f"Shipment {self.tracking_code}"
    
    def save(self, *args, **kwargs):
        # Calculate total fee if not set
        if not self.total_fee:
            self.total_fee = self.shipping_fee + self.insurance_fee + self.cod_fee
        super().save(*args, **kwargs)
    
    # --- Computed Properties ---
    
    @property
    def is_delivered(self) -> bool:
        return self.status == self.Status.DELIVERED
    
    @property
    def is_failed(self) -> bool:
        return self.status in [self.Status.FAILED, self.Status.EXCEPTION]
    
    @property
    def is_returned(self) -> bool:
        return self.status in [
            self.Status.WAITING_RETURN,
            self.Status.RETURNING,
            self.Status.RETURNED
        ]
    
    @property
    def is_active(self) -> bool:
        """Check if shipment is still in active transport."""
        return self.status in [
            self.Status.PENDING,
            self.Status.PICKING,
            self.Status.PICKED_UP,
            self.Status.IN_TRANSIT,
            self.Status.SORTING,
            self.Status.OUT_FOR_DELIVERY
        ]
    
    @property
    def is_final(self) -> bool:
        """Check if shipment is in final state."""
        return self.status in [
            self.Status.DELIVERED,
            self.Status.RETURNED,
            self.Status.CANCELLED
        ]
    
    @property
    def can_cancel(self) -> bool:
        """Check if shipment can be cancelled."""
        return self.status in [self.Status.PENDING, self.Status.PICKING]
    
    @property
    def can_retry(self) -> bool:
        """Check if delivery can be retried."""
        return (
            self.status == self.Status.FAILED and
            self.delivery_attempts < self.max_delivery_attempts
        )
    
    @property
    def days_in_transit(self) -> int:
        """Days since shipment was created."""
        if self.picked_up_at:
            if self.delivered_at:
                delta = self.delivered_at - self.picked_up_at
            else:
                delta = timezone.now() - self.picked_up_at
            return delta.days
        return 0
    
    @property
    def tracking_url(self) -> str:
        """Get tracking URL for provider."""
        urls = {
            'ghn': f'https://donhang.ghn.vn/?order_code={self.tracking_code}',
            'ghtk': f'https://i.ghtk.vn/{self.tracking_code}',
            'vtp': f'https://viettelpost.vn/tra-cuu?code={self.tracking_code}',
        }
        return urls.get(self.provider, '')
    
    # --- Status Update Methods ---
    
    def update_status(
        self,
        new_status: str,
        provider_status: str = '',
        location: str = '',
        description: str = '',
        timestamp: timezone.datetime = None
    ) -> 'ShipmentEvent':
        """
        Update shipment status and log event.
        
        Returns created ShipmentEvent.
        """
        old_status = self.status
        self.status = new_status
        self.provider_status = provider_status or new_status
        self.last_location = location
        self.last_status_update = timestamp or timezone.now()
        
        # Set timestamps based on status
        now = timestamp or timezone.now()
        
        if new_status == self.Status.PICKED_UP and not self.picked_up_at:
            self.picked_up_at = now
        elif new_status == self.Status.DELIVERED and not self.delivered_at:
            self.delivered_at = now
            self.cod_collected = True
        elif new_status == self.Status.RETURNED and not self.returned_at:
            self.returned_at = now
        elif new_status == self.Status.CANCELLED and not self.cancelled_at:
            self.cancelled_at = now
        elif new_status == self.Status.FAILED:
            self.delivery_attempts += 1
        
        self.save()
        
        # Create event log
        event = ShipmentEvent.objects.create(
            shipment=self,
            status=provider_status or new_status,
            description=description or f"Status: {new_status}",
            location=location,
            occurred_at=now
        )
        
        return event
    
    def mark_delivered(self, timestamp=None) -> None:
        """Mark shipment as delivered."""
        self.update_status(
            self.Status.DELIVERED,
            description='Giao hàng thành công',
            timestamp=timestamp
        )
    
    def mark_failed(self, reason: str, timestamp=None) -> None:
        """Mark delivery as failed."""
        self.fail_reason = reason
        self.update_status(
            self.Status.FAILED,
            description=f'Giao thất bại: {reason}',
            timestamp=timestamp
        )
    
    def mark_returned(self, reason: str = '', timestamp=None) -> None:
        """Mark shipment as returned."""
        self.update_status(
            self.Status.RETURNED,
            description=f'Đã trả hàng về shop{": " + reason if reason else ""}',
            timestamp=timestamp
        )
    
    def cancel(self, reason: str = '') -> bool:
        """Cancel shipment."""
        if not self.can_cancel:
            return False
        
        self.cancel_reason = reason
        self.update_status(
            self.Status.CANCELLED,
            description=f'Đã hủy vận đơn{": " + reason if reason else ""}'
        )
        return True


class ShipmentEvent(TimeStampedModel):
    """
    Tracking event log.
    
    Stores detailed history of shipment status updates
    from provider webhooks.
    """
    
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='Vận chuyển'
    )
    status = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name='Trạng thái'
    )
    description = models.TextField(
        verbose_name='Mô tả'
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Vị trí'
    )
    occurred_at = models.DateTimeField(
        db_index=True,
        verbose_name='Thời điểm'
    )
    
    # Raw provider data
    provider_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Dữ liệu gốc'
    )
    
    class Meta:
        verbose_name = 'Sự kiện vận chuyển'
        verbose_name_plural = 'Sự kiện vận chuyển'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['shipment', '-occurred_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.shipment.tracking_code}: {self.status}"


class DeliveryAttempt(TimeStampedModel):
    """
    Failed delivery attempt record.
    
    Tracks each failed delivery attempt with reason
    and follow-up actions.
    """
    
    class FailReason(models.TextChoices):
        NOT_HOME = 'not_home', 'Không có người nhận'
        WRONG_ADDRESS = 'wrong_address', 'Sai địa chỉ'
        PHONE_UNREACHABLE = 'phone_unreachable', 'Không liên lạc được'
        REFUSED = 'refused', 'Từ chối nhận hàng'
        INSUFFICIENT_COD = 'insufficient_cod', 'Không đủ tiền COD'
        RESCHEDULED = 'rescheduled', 'Hẹn giao lại'
        WEATHER = 'weather', 'Thời tiết xấu'
        OTHER = 'other', 'Lý do khác'
    
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name='attempt_logs',
        verbose_name='Vận chuyển'
    )
    attempt_number = models.PositiveIntegerField(
        verbose_name='Lần giao thứ'
    )
    attempted_at = models.DateTimeField(
        verbose_name='Thời điểm giao'
    )
    fail_reason = models.CharField(
        max_length=20,
        choices=FailReason.choices,
        verbose_name='Lý do thất bại'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Ghi chú'
    )
    
    # Rescheduled delivery
    rescheduled_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Lịch giao lại'
    )
    
    class Meta:
        verbose_name = 'Lần giao hàng'
        verbose_name_plural = 'Các lần giao hàng'
        ordering = ['shipment', 'attempt_number']
        unique_together = ['shipment', 'attempt_number']
    
    def __str__(self) -> str:
        return f"{self.shipment.tracking_code} - Attempt #{self.attempt_number}"


class CODReconciliation(TimeStampedModel):
    """
    COD reconciliation record.
    
    Tracks COD money transfer from provider to shop.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ đối soát'
        CONFIRMED = 'confirmed', 'Đã xác nhận'
        TRANSFERRED = 'transferred', 'Đã chuyển tiền'
        DISPUTED = 'disputed', 'Có tranh chấp'
    
    provider = models.CharField(
        max_length=20,
        choices=Shipment.Provider.choices,
        verbose_name='Nhà vận chuyển'
    )
    reconciliation_date = models.DateField(
        db_index=True,
        verbose_name='Ngày đối soát'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Trạng thái'
    )
    
    # Amounts
    total_orders = models.PositiveIntegerField(
        default=0,
        verbose_name='Tổng đơn'
    )
    total_cod = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name='Tổng tiền COD'
    )
    total_shipping_fee = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name='Tổng phí ship'
    )
    net_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name='Số tiền thực nhận'
    )
    
    # Bank transfer info
    transferred_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Thời điểm chuyển khoản'
    )
    transfer_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Mã chuyển khoản'
    )
    
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    # Link to shipments
    shipments = models.ManyToManyField(
        Shipment,
        related_name='cod_reconciliations',
        blank=True,
        verbose_name='Đơn hàng'
    )
    
    class Meta:
        verbose_name = 'Đối soát COD'
        verbose_name_plural = 'Đối soát COD'
        ordering = ['-reconciliation_date']
        unique_together = ['provider', 'reconciliation_date']
    
    def __str__(self) -> str:
        return f"{self.get_provider_display()} - {self.reconciliation_date}"
