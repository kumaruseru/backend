"""
Store Inventory - Production-Ready Models.

Comprehensive stock tracking with:
- StockItem: Per-product stock with reservation support
- StockMovement: Complete audit trail
- StockAlert: Low stock notifications
- BatchInventory: Batch/lot tracking for expiry
- Warehouse: Multi-location support
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, F

from apps.common.core.models import TimeStampedModel, UUIDModel


class Warehouse(TimeStampedModel):
    """
    Warehouse/location for multi-location inventory.
    """
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Tên kho')
    code = models.CharField(max_length=20, unique=True, verbose_name='Mã kho')
    address = models.TextField(blank=True, verbose_name='Địa chỉ')
    
    # Contact
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='Hoạt động')
    is_default = models.BooleanField(default=False, verbose_name='Kho mặc định')
    
    # Settings
    allow_negative_stock = models.BooleanField(default=False, verbose_name='Cho phép âm kho')
    
    class Meta:
        verbose_name = 'Kho hàng'
        verbose_name_plural = 'Kho hàng'
        ordering = ['-is_default', 'name']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            Warehouse.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def total_stock_value(self) -> Decimal:
        """Calculate total stock value in this warehouse."""
        from apps.store.catalog.models import Product
        
        result = self.stock_items.filter(
            product__is_active=True
        ).aggregate(
            total=Sum(F('quantity') * F('product__price'))
        )
        return result['total'] or Decimal('0')


class StockItem(TimeStampedModel):
    """
    Stock tracking for products.
    
    Tracks:
    - Current quantity
    - Reserved quantity (for pending orders)
    - Low stock threshold for alerts
    - Reorder point and quantity
    """
    
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='stock',
        verbose_name='Sản phẩm'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='stock_items',
        null=True,
        blank=True,
        verbose_name='Kho'
    )
    
    # Stock levels
    quantity = models.IntegerField(
        default=0,
        verbose_name='Số lượng tồn kho'
    )
    reserved_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Đã đặt trước',
        help_text='Số lượng đang chờ xử lý đơn hàng'
    )
    
    # Thresholds
    low_stock_threshold = models.PositiveIntegerField(
        default=10,
        verbose_name='Ngưỡng cảnh báo'
    )
    reorder_point = models.PositiveIntegerField(
        default=5,
        verbose_name='Điểm đặt hàng lại'
    )
    reorder_quantity = models.PositiveIntegerField(
        default=50,
        verbose_name='Số lượng đặt lại'
    )
    
    # Tracking
    last_restocked_at = models.DateTimeField(null=True, blank=True, verbose_name='Nhập hàng cuối')
    last_sold_at = models.DateTimeField(null=True, blank=True, verbose_name='Bán hàng cuối')
    
    # Cost tracking
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name='Giá vốn đơn vị'
    )
    
    class Meta:
        verbose_name = 'Tồn kho'
        verbose_name_plural = 'Tồn kho'
        unique_together = [['product', 'warehouse']]
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['warehouse', 'quantity']),
        ]
    
    def __str__(self) -> str:
        return f"Stock: {self.product.name} ({self.available_quantity})"
    
    # --- Properties ---
    
    @property
    def available_quantity(self) -> int:
        """Available quantity (total - reserved)."""
        return max(0, self.quantity - self.reserved_quantity)
    
    # Alias for backward compatibility
    @property
    def available(self) -> int:
        return self.available_quantity
    
    @property
    def reserved(self) -> int:
        """Alias for reserved_quantity."""
        return self.reserved_quantity
    
    @property
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.available_quantity > 0
    
    @property
    def is_low_stock(self) -> bool:
        """Check if stock is below threshold."""
        return 0 < self.available_quantity <= self.low_stock_threshold
    
    @property
    def is_out_of_stock(self) -> bool:
        """Check if completely out of stock."""
        return self.available_quantity <= 0
    
    @property
    def needs_reorder(self) -> bool:
        """Check if stock is at reorder point."""
        return self.available_quantity <= self.reorder_point
    
    @property
    def stock_value(self) -> Decimal:
        """Calculate stock value."""
        if self.unit_cost:
            return self.unit_cost * self.quantity
        return self.product.current_price * self.quantity
    
    @property
    def stock_status(self) -> str:
        """Get stock status label."""
        if self.is_out_of_stock:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        return 'in_stock'
    
    # --- Operations ---
    
    def reserve(self, quantity: int, reference: str = '', user=None) -> bool:
        """
        Reserve stock for an order.
        
        Returns True if successful, False if insufficient stock.
        """
        if quantity > self.available_quantity:
            return False
        
        self.reserved_quantity += quantity
        self.save(update_fields=['reserved_quantity', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.RESERVE,
            quantity_change=-quantity,
            reason=StockMovement.Reason.RESERVATION,
            reference=reference,
            notes=f'Reserved {quantity} units',
            created_by=user
        )
        
        return True
    
    def release(self, quantity: int, reference: str = '', user=None) -> int:
        """
        Release reserved stock (e.g., order cancelled).
        
        Returns the amount actually released.
        """
        release_amount = min(quantity, self.reserved_quantity)
        self.reserved_quantity -= release_amount
        self.save(update_fields=['reserved_quantity', 'updated_at'])
        
        if release_amount > 0:
            StockMovement.objects.create(
                stock=self,
                movement_type=StockMovement.Type.RELEASE,
                quantity_change=release_amount,
                reason=StockMovement.Reason.RELEASE,
                reference=reference,
                notes=f'Released {release_amount} reserved units',
                created_by=user
            )
        
        return release_amount
    
    def confirm_sale(self, quantity: int, reference: str = '', user=None) -> None:
        """Confirm sale and deduct from stock."""
        reserved_to_deduct = min(quantity, self.reserved_quantity)
        self.reserved_quantity -= reserved_to_deduct
        self.quantity -= quantity
        self.last_sold_at = timezone.now()
        self.save(update_fields=['quantity', 'reserved_quantity', 'last_sold_at', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.OUT,
            quantity_change=-quantity,
            quantity_before=self.quantity + quantity,
            quantity_after=self.quantity,
            reason=StockMovement.Reason.SALE,
            reference=reference,
            notes=f'Sold {quantity} units',
            created_by=user
        )
        
        # Check for low stock alert
        self._check_stock_alert()
    
    def add_stock(
        self,
        quantity: int,
        reference: str = '',
        notes: str = '',
        unit_cost: Decimal = None,
        user=None
    ) -> None:
        """Add stock (restock/purchase)."""
        old_quantity = self.quantity
        self.quantity += quantity
        self.last_restocked_at = timezone.now()
        
        if unit_cost:
            # Update unit cost with weighted average
            if self.unit_cost and old_quantity > 0:
                total_cost = (self.unit_cost * old_quantity) + (unit_cost * quantity)
                self.unit_cost = total_cost / self.quantity
            else:
                self.unit_cost = unit_cost
        
        self.save(update_fields=['quantity', 'last_restocked_at', 'unit_cost', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.IN,
            quantity_change=quantity,
            quantity_before=old_quantity,
            quantity_after=self.quantity,
            reason=StockMovement.Reason.PURCHASE,
            reference=reference,
            unit_cost=unit_cost,
            notes=notes or f'Added {quantity} units',
            created_by=user
        )
        
        # Clear any out-of-stock alerts
        self._clear_stock_alert()
    
    def adjust_stock(
        self,
        new_quantity: int,
        reason: str = '',
        notes: str = '',
        user=None
    ) -> None:
        """Adjust stock to specific quantity (inventory count)."""
        old_quantity = self.quantity
        difference = new_quantity - old_quantity
        
        self.quantity = new_quantity
        self.save(update_fields=['quantity', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.ADJUSTMENT,
            quantity_change=difference,
            quantity_before=old_quantity,
            quantity_after=new_quantity,
            reason=reason or StockMovement.Reason.ADJUSTMENT,
            notes=notes or f'Adjusted from {old_quantity} to {new_quantity}',
            created_by=user
        )
        
        self._check_stock_alert()
    
    def process_return(self, quantity: int, reference: str = '', user=None) -> None:
        """Process returned items back to stock."""
        old_quantity = self.quantity
        self.quantity += quantity
        self.save(update_fields=['quantity', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.IN,
            quantity_change=quantity,
            quantity_before=old_quantity,
            quantity_after=self.quantity,
            reason=StockMovement.Reason.RETURN,
            reference=reference,
            notes=f'Returned {quantity} units',
            created_by=user
        )
        
        self._clear_stock_alert()
    
    def mark_damaged(self, quantity: int, notes: str = '', user=None) -> None:
        """Mark items as damaged/lost."""
        if quantity > self.quantity:
            quantity = self.quantity
        
        old_quantity = self.quantity
        self.quantity -= quantity
        self.save(update_fields=['quantity', 'updated_at'])
        
        StockMovement.objects.create(
            stock=self,
            movement_type=StockMovement.Type.OUT,
            quantity_change=-quantity,
            quantity_before=old_quantity,
            quantity_after=self.quantity,
            reason=StockMovement.Reason.DAMAGE,
            notes=notes or f'Damaged/lost {quantity} units',
            created_by=user
        )
        
        self._check_stock_alert()
    
    def _check_stock_alert(self):
        """Check and create stock alerts if needed."""
        if self.is_out_of_stock:
            StockAlert.objects.update_or_create(
                stock=self,
                alert_type=StockAlert.Type.OUT_OF_STOCK,
                is_resolved=False,
                defaults={'threshold': 0, 'current_quantity': self.quantity}
            )
        elif self.is_low_stock:
            StockAlert.objects.update_or_create(
                stock=self,
                alert_type=StockAlert.Type.LOW_STOCK,
                is_resolved=False,
                defaults={
                    'threshold': self.low_stock_threshold,
                    'current_quantity': self.available_quantity
                }
            )
    
    def _clear_stock_alert(self):
        """Clear stock alerts when stock is replenished."""
        if self.available_quantity > self.low_stock_threshold:
            StockAlert.objects.filter(
                stock=self,
                is_resolved=False
            ).update(is_resolved=True, resolved_at=timezone.now())


class StockMovement(TimeStampedModel):
    """
    Audit log for stock changes.
    
    Records all stock movements for inventory tracking and reporting.
    """
    
    class Type(models.TextChoices):
        IN = 'in', 'Nhập'
        OUT = 'out', 'Xuất'
        RESERVE = 'reserve', 'Đặt trước'
        RELEASE = 'release', 'Giải phóng'
        ADJUSTMENT = 'adjustment', 'Điều chỉnh'
        TRANSFER = 'transfer', 'Chuyển kho'
    
    class Reason(models.TextChoices):
        PURCHASE = 'purchase', 'Nhập hàng'
        SALE = 'sale', 'Bán hàng'
        RETURN = 'return', 'Trả hàng'
        ADJUSTMENT = 'adjustment', 'Điều chỉnh'
        RESERVATION = 'reservation', 'Đặt trước'
        RELEASE = 'release', 'Giải phóng'
        DAMAGE = 'damage', 'Hư hỏng/Mất'
        TRANSFER_IN = 'transfer_in', 'Nhận chuyển kho'
        TRANSFER_OUT = 'transfer_out', 'Chuyển kho đi'
        INITIAL = 'initial', 'Tồn kho đầu'
        EXPIRED = 'expired', 'Hết hạn'
    
    stock = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name='Kho'
    )
    
    movement_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.ADJUSTMENT,
        verbose_name='Loại'
    )
    quantity_change = models.IntegerField(
        verbose_name='Thay đổi số lượng',
        help_text='Dương = nhập, Âm = xuất'
    )
    quantity_before = models.IntegerField(
        null=True, blank=True,
        verbose_name='SL trước'
    )
    quantity_after = models.IntegerField(
        null=True, blank=True,
        verbose_name='SL sau'
    )
    
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        verbose_name='Lý do'
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Tham chiếu',
        help_text='Mã đơn hàng, mã nhập hàng, v.v.'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    # Cost tracking
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name='Giá vốn đơn vị'
    )
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Người thực hiện'
    )
    
    class Meta:
        verbose_name = 'Lịch sử kho'
        verbose_name_plural = 'Lịch sử kho'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', '-created_at']),
            models.Index(fields=['reason', '-created_at']),
            models.Index(fields=['reference']),
        ]
    
    def __str__(self) -> str:
        sign = '+' if self.quantity_change > 0 else ''
        return f"{self.stock.product.name}: {sign}{self.quantity_change}"
    
    @property
    def is_incoming(self) -> bool:
        return self.quantity_change > 0
    
    @property
    def is_outgoing(self) -> bool:
        return self.quantity_change < 0


class StockAlert(TimeStampedModel):
    """
    Stock alerts for notifications.
    """
    
    class Type(models.TextChoices):
        LOW_STOCK = 'low_stock', 'Sắp hết hàng'
        OUT_OF_STOCK = 'out_of_stock', 'Hết hàng'
        REORDER = 'reorder', 'Cần đặt hàng'
        EXPIRING = 'expiring', 'Sắp hết hạn'
    
    stock = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name='Kho'
    )
    alert_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name='Loại cảnh báo'
    )
    threshold = models.PositiveIntegerField(default=0, verbose_name='Ngưỡng')
    current_quantity = models.IntegerField(verbose_name='SL hiện tại')
    
    is_resolved = models.BooleanField(default=False, verbose_name='Đã xử lý')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Xử lý lúc')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Người xử lý'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    class Meta:
        verbose_name = 'Cảnh báo tồn kho'
        verbose_name_plural = 'Cảnh báo tồn kho'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.get_alert_type_display()}: {self.stock.product.name}"
    
    def resolve(self, user=None, notes: str = ''):
        """Mark alert as resolved."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if notes:
            self.notes = notes
        self.save()


class InventoryCount(UUIDModel):
    """
    Inventory count/audit session.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        IN_PROGRESS = 'in_progress', 'Đang kiểm'
        COMPLETED = 'completed', 'Hoàn thành'
        CANCELLED = 'cancelled', 'Đã hủy'
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='inventory_counts',
        null=True, blank=True,
        verbose_name='Kho'
    )
    
    name = models.CharField(max_length=100, verbose_name='Tên đợt kiểm')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Trạng thái'
    )
    
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Bắt đầu')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Hoàn thành')
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_counts',
        verbose_name='Người tạo'
    )
    notes = models.TextField(blank=True, verbose_name='Ghi chú')
    
    class Meta:
        verbose_name = 'Đợt kiểm kho'
        verbose_name_plural = 'Đợt kiểm kho'
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return self.name
    
    def start(self):
        """Start the inventory count."""
        self.status = self.Status.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])
    
    def complete(self, apply_adjustments: bool = True):
        """Complete the inventory count."""
        if apply_adjustments:
            for item in self.items.all():
                if item.variance != 0:
                    item.stock.adjust_stock(
                        new_quantity=item.counted_quantity,
                        reason=StockMovement.Reason.ADJUSTMENT,
                        notes=f'Inventory count: {self.name}'
                    )
        
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class InventoryCountItem(TimeStampedModel):
    """
    Individual product count in an inventory count session.
    """
    
    inventory_count = models.ForeignKey(
        InventoryCount,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Đợt kiểm'
    )
    stock = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='count_items',
        verbose_name='Sản phẩm'
    )
    
    system_quantity = models.IntegerField(verbose_name='SL hệ thống')
    counted_quantity = models.IntegerField(null=True, blank=True, verbose_name='SL thực tế')
    
    notes = models.TextField(blank=True)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Người kiểm'
    )
    counted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Chi tiết kiểm kho'
        verbose_name_plural = 'Chi tiết kiểm kho'
        unique_together = [['inventory_count', 'stock']]
    
    @property
    def variance(self) -> int:
        """Difference between counted and system quantity."""
        if self.counted_quantity is None:
            return 0
        return self.counted_quantity - self.system_quantity
    
    @property
    def variance_value(self) -> Decimal:
        """Value of variance."""
        return self.variance * self.stock.product.current_price
