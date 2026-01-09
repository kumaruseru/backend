"""Store Inventory - Stock Management Models."""
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, F
from apps.common.core.models import TimeStampedModel, UUIDModel


class Warehouse(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='Name')
    code = models.CharField(max_length=20, unique=True, verbose_name='Code')
    address = models.TextField(blank=True, verbose_name='Address')
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, verbose_name='Active')
    is_default = models.BooleanField(default=False, verbose_name='Default')
    allow_negative_stock = models.BooleanField(default=False, verbose_name='Allow Negative Stock')

    class Meta:
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'
        ordering = ['-is_default', 'name']

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.is_default:
            Warehouse.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def total_stock_value(self) -> Decimal:
        result = self.stock_items.filter(product__is_active=True).aggregate(total=Sum(F('quantity') * F('product__price')))
        return result['total'] or Decimal('0')


class StockItem(TimeStampedModel):
    product = models.OneToOneField('catalog.Product', on_delete=models.CASCADE, related_name='stock', verbose_name='Product')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stock_items', null=True, blank=True, verbose_name='Warehouse')
    quantity = models.IntegerField(default=0, verbose_name='Quantity')
    reserved_quantity = models.PositiveIntegerField(default=0, verbose_name='Reserved Quantity', help_text='Reserved for pending orders')
    low_stock_threshold = models.PositiveIntegerField(default=10, verbose_name='Low Stock Threshold')
    reorder_point = models.PositiveIntegerField(default=5, verbose_name='Reorder Point')
    reorder_quantity = models.PositiveIntegerField(default=50, verbose_name='Reorder Quantity')
    last_restocked_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Restocked')
    last_sold_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Sold')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Unit Cost')

    class Meta:
        verbose_name = 'Stock Item'
        verbose_name_plural = 'Stock Items'
        unique_together = [['product', 'warehouse']]
        indexes = [models.Index(fields=['product']), models.Index(fields=['warehouse', 'quantity'])]

    def __str__(self) -> str:
        return f"Stock: {self.product.name} ({self.available_quantity})"

    @property
    def available_quantity(self) -> int:
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def available(self) -> int:
        return self.available_quantity

    @property
    def reserved(self) -> int:
        return self.reserved_quantity

    @property
    def is_in_stock(self) -> bool:
        return self.available_quantity > 0

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.available_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.available_quantity <= 0

    @property
    def needs_reorder(self) -> bool:
        return self.available_quantity <= self.reorder_point

    @property
    def stock_value(self) -> Decimal:
        if self.unit_cost:
            return self.unit_cost * self.quantity
        return self.product.current_price * self.quantity

    @property
    def stock_status(self) -> str:
        if self.is_out_of_stock:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        return 'in_stock'

    def reserve(self, quantity: int, reference: str = '', user=None) -> bool:
        """
        Reserve stock atomically using select_for_update to prevent race conditions.
        Returns True if reservation successful, False otherwise.
        """
        with transaction.atomic():
            # Lock this row for update to prevent race conditions
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            if quantity > locked_stock.available_quantity:
                return False
            # Use F() expression for atomic update
            StockItem.objects.filter(pk=self.pk).update(
                reserved_quantity=F('reserved_quantity') + quantity,
                updated_at=timezone.now()
            )
            self.refresh_from_db()
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
        Release reserved stock atomically.
        Returns the amount actually released.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            release_amount = min(quantity, locked_stock.reserved_quantity)
            if release_amount > 0:
                StockItem.objects.filter(pk=self.pk).update(
                    reserved_quantity=F('reserved_quantity') - release_amount,
                    updated_at=timezone.now()
                )
                self.refresh_from_db()
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
        """
        Confirm a sale atomically - deduct from reserved and actual quantity.
        Uses select_for_update to prevent overselling.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            reserved_to_deduct = min(quantity, locked_stock.reserved_quantity)
            quantity_before = locked_stock.quantity
            
            # Atomic update using F() expressions
            StockItem.objects.filter(pk=self.pk).update(
                quantity=F('quantity') - quantity,
                reserved_quantity=F('reserved_quantity') - reserved_to_deduct,
                last_sold_at=timezone.now(),
                updated_at=timezone.now()
            )
            self.refresh_from_db()
            
            StockMovement.objects.create(
                stock=self, 
                movement_type=StockMovement.Type.OUT, 
                quantity_change=-quantity, 
                quantity_before=quantity_before, 
                quantity_after=self.quantity, 
                reason=StockMovement.Reason.SALE, 
                reference=reference, 
                notes=f'Sold {quantity} units', 
                created_by=user
            )
            self._check_stock_alert()

    def add_stock(self, quantity: int, reference: str = '', notes: str = '', unit_cost: Decimal = None, user=None) -> None:
        """
        Add stock atomically using F() expression to prevent race conditions.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            old_quantity = locked_stock.quantity
            
            # Calculate new weighted average cost
            new_unit_cost = None
            if unit_cost:
                if locked_stock.unit_cost and old_quantity > 0:
                    total_cost = (locked_stock.unit_cost * old_quantity) + (unit_cost * quantity)
                    new_unit_cost = total_cost / (old_quantity + quantity)
                else:
                    new_unit_cost = unit_cost
            
            # Build update dict
            update_fields = {
                'quantity': F('quantity') + quantity,
                'last_restocked_at': timezone.now(),
                'updated_at': timezone.now()
            }
            if new_unit_cost is not None:
                update_fields['unit_cost'] = new_unit_cost
            
            StockItem.objects.filter(pk=self.pk).update(**update_fields)
            self.refresh_from_db()
            
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
            self._clear_stock_alert()

    def adjust_stock(self, new_quantity: int, reason: str = '', notes: str = '', user=None) -> None:
        """
        Adjust stock to a specific quantity atomically.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            old_quantity = locked_stock.quantity
            difference = new_quantity - old_quantity
            
            StockItem.objects.filter(pk=self.pk).update(
                quantity=new_quantity,
                updated_at=timezone.now()
            )
            self.refresh_from_db()
            
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
        """
        Process a return atomically - add quantity back to stock.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            old_quantity = locked_stock.quantity
            
            StockItem.objects.filter(pk=self.pk).update(
                quantity=F('quantity') + quantity,
                updated_at=timezone.now()
            )
            self.refresh_from_db()
            
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
        """
        Mark stock as damaged/lost atomically.
        """
        with transaction.atomic():
            locked_stock = StockItem.objects.select_for_update().get(pk=self.pk)
            # Clamp quantity to available
            actual_qty = min(quantity, locked_stock.quantity)
            if actual_qty <= 0:
                return
            old_quantity = locked_stock.quantity
            
            StockItem.objects.filter(pk=self.pk).update(
                quantity=F('quantity') - actual_qty,
                updated_at=timezone.now()
            )
            self.refresh_from_db()
            
            StockMovement.objects.create(
                stock=self, 
                movement_type=StockMovement.Type.OUT, 
                quantity_change=-actual_qty, 
                quantity_before=old_quantity, 
                quantity_after=self.quantity, 
                reason=StockMovement.Reason.DAMAGE, 
                notes=notes or f'Damaged/lost {actual_qty} units', 
                created_by=user
            )
            self._check_stock_alert()

    def _check_stock_alert(self):
        if self.is_out_of_stock:
            StockAlert.objects.update_or_create(stock=self, alert_type=StockAlert.Type.OUT_OF_STOCK, is_resolved=False, defaults={'threshold': 0, 'current_quantity': self.quantity})
        elif self.is_low_stock:
            StockAlert.objects.update_or_create(stock=self, alert_type=StockAlert.Type.LOW_STOCK, is_resolved=False, defaults={'threshold': self.low_stock_threshold, 'current_quantity': self.available_quantity})

    def _clear_stock_alert(self):
        if self.available_quantity > self.low_stock_threshold:
            StockAlert.objects.filter(stock=self, is_resolved=False).update(is_resolved=True, resolved_at=timezone.now())


class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT = 'out', 'Stock Out'
        RESERVE = 'reserve', 'Reserve'
        RELEASE = 'release', 'Release'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        TRANSFER = 'transfer', 'Transfer'

    class Reason(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        SALE = 'sale', 'Sale'
        RETURN = 'return', 'Return'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        RESERVATION = 'reservation', 'Reservation'
        RELEASE = 'release', 'Release'
        DAMAGE = 'damage', 'Damage/Loss'
        TRANSFER_IN = 'transfer_in', 'Transfer In'
        TRANSFER_OUT = 'transfer_out', 'Transfer Out'
        INITIAL = 'initial', 'Initial Stock'
        EXPIRED = 'expired', 'Expired'

    stock = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='movements', verbose_name='Stock')
    movement_type = models.CharField(max_length=20, choices=Type.choices, default=Type.ADJUSTMENT, verbose_name='Type')
    quantity_change = models.IntegerField(verbose_name='Quantity Change', help_text='Positive=in, Negative=out')
    quantity_before = models.IntegerField(null=True, blank=True, verbose_name='Qty Before')
    quantity_after = models.IntegerField(null=True, blank=True, verbose_name='Qty After')
    reason = models.CharField(max_length=20, choices=Reason.choices, verbose_name='Reason')
    reference = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='Reference', help_text='Order ID, PO number, etc.')
    notes = models.TextField(blank=True, verbose_name='Notes')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Unit Cost')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Created By')

    class Meta:
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['stock', '-created_at']), models.Index(fields=['reason', '-created_at']), models.Index(fields=['reference'])]

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
    class Type(models.TextChoices):
        LOW_STOCK = 'low_stock', 'Low Stock'
        OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'
        REORDER = 'reorder', 'Needs Reorder'
        EXPIRING = 'expiring', 'Expiring Soon'

    stock = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='alerts', verbose_name='Stock')
    alert_type = models.CharField(max_length=20, choices=Type.choices, verbose_name='Alert Type')
    threshold = models.PositiveIntegerField(default=0, verbose_name='Threshold')
    current_quantity = models.IntegerField(verbose_name='Current Quantity')
    is_resolved = models.BooleanField(default=False, verbose_name='Resolved')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Resolved At')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Resolved By')
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Stock Alert'
        verbose_name_plural = 'Stock Alerts'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.get_alert_type_display()}: {self.stock.product.name}"

    def resolve(self, user=None, notes: str = ''):
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if notes:
            self.notes = notes
        self.save()


class InventoryCount(UUIDModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='inventory_counts', null=True, blank=True, verbose_name='Warehouse')
    name = models.CharField(max_length=100, verbose_name='Name')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name='Status')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Started At')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='inventory_counts', verbose_name='Created By')
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Inventory Count'
        verbose_name_plural = 'Inventory Counts'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.name

    def start(self):
        self.status = self.Status.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

    def complete(self, apply_adjustments: bool = True):
        if apply_adjustments:
            for item in self.items.all():
                if item.variance != 0:
                    item.stock.adjust_stock(new_quantity=item.counted_quantity, reason=StockMovement.Reason.ADJUSTMENT, notes=f'Inventory count: {self.name}')
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class InventoryCountItem(TimeStampedModel):
    inventory_count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name='items', verbose_name='Inventory Count')
    stock = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='count_items', verbose_name='Stock')
    system_quantity = models.IntegerField(verbose_name='System Quantity')
    counted_quantity = models.IntegerField(null=True, blank=True, verbose_name='Counted Quantity')
    notes = models.TextField(blank=True)
    counted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Counted By')
    counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Inventory Count Item'
        verbose_name_plural = 'Inventory Count Items'
        unique_together = [['inventory_count', 'stock']]

    @property
    def variance(self) -> int:
        if self.counted_quantity is None:
            return 0
        return self.counted_quantity - self.system_quantity

    @property
    def variance_value(self) -> Decimal:
        return self.variance * self.stock.product.current_price
