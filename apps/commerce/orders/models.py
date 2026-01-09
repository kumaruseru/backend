"""Commerce Orders - Order Management Models."""
import uuid
import time
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class Order(UUIDModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        READY_TO_SHIP = 'ready_to_ship', 'Ready to Ship'
        SHIPPING = 'shipping', 'Shipping'
        DELIVERED = 'delivered', 'Delivered'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
        FAILED = 'failed', 'Failed'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PENDING = 'pending', 'Processing'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Payment Failed'
        PARTIAL_REFUND = 'partial_refund', 'Partial Refund'
        REFUNDED = 'refunded', 'Refunded'

    class PaymentMethod(models.TextChoices):
        COD = 'cod', 'Cash on Delivery'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'MoMo'
        STRIPE = 'stripe', 'Stripe (Card)'

    class Source(models.TextChoices):
        WEB = 'web', 'Website'
        MOBILE_APP = 'mobile', 'Mobile App'
        ADMIN = 'admin', 'Admin Created'
        API = 'api', 'API'

    order_number = models.CharField(max_length=20, unique=True, editable=False, db_index=True, verbose_name='Order Number')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders', verbose_name='Customer')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name='Status')
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WEB, verbose_name='Source')

    # Shipping address
    recipient_name = models.CharField(max_length=100, verbose_name='Recipient Name')
    phone = models.CharField(max_length=15, db_index=True, verbose_name='Phone')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.CharField(max_length=255, verbose_name='Address')
    ward = models.CharField(max_length=100, verbose_name='Ward')
    district = models.CharField(max_length=100, verbose_name='District')
    city = models.CharField(max_length=100, verbose_name='City')
    country = models.CharField(max_length=50, default='Vietnam', verbose_name='Country')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='Postal Code')
    district_id = models.IntegerField(null=True, blank=True, verbose_name='GHN District ID')
    ward_code = models.CharField(max_length=20, blank=True, verbose_name='GHN Ward Code')

    # Payment
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD, db_index=True, verbose_name='Payment Method')
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True, verbose_name='Payment Status')

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Subtotal')
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Shipping Fee')
    insurance_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Insurance Fee')
    discount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Discount')
    tax = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Tax')
    total = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Total')
    currency = models.CharField(max_length=3, default='VND', verbose_name='Currency')

    # Coupon
    coupon_code = models.CharField(max_length=50, blank=True, verbose_name='Coupon Code')
    coupon_discount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Coupon Discount')

    # Tracking
    tracking_code = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='Tracking Code')
    shipping_provider = models.CharField(max_length=20, blank=True, verbose_name='Shipping Provider')

    # Notes
    customer_note = models.TextField(blank=True, verbose_name='Customer Note')
    admin_note = models.TextField(blank=True, verbose_name='Admin Note')

    # Flags
    is_priority = models.BooleanField(default=False, verbose_name='Priority Order')
    is_gift = models.BooleanField(default=False, verbose_name='Gift Order')
    gift_message = models.TextField(blank=True, verbose_name='Gift Message')

    # Timestamps
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='Confirmed At')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Paid At')
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name='Shipped At')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='Delivered At')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Cancelled At')

    # Cancellation
    cancel_reason = models.TextField(blank=True, verbose_name='Cancel Reason')
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_orders', verbose_name='Cancelled By')

    # Analytics
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at']), models.Index(fields=['status', '-created_at']), models.Index(fields=['payment_status', '-created_at'])]
        permissions = [('can_view_all_orders', 'Can view all orders'), ('can_cancel_orders', 'Can cancel orders'), ('can_refund_orders', 'Can refund orders')]

    def __str__(self) -> str:
        return f"Order #{self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number() -> str:
        """
        Generate unique order number in format: YYMMDD-XXXXXX
        
        - YYMMDD: Date component for human readability
        - XXXXXX: Random hex for security (can't guess order volume)
        
        Example: 260109-A7F3B2 (January 9, 2026)
        """
        import secrets
        from datetime import datetime
        date_part = datetime.now().strftime('%y%m%d')
        random_part = secrets.token_hex(3).upper()  # 6 chars
        return f"{date_part}-{random_part}"

    @property
    def full_address(self) -> str:
        parts = [self.address, self.ward, self.district, self.city]
        return ', '.join(filter(None, parts))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def can_cancel(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]

    @property
    def can_refund(self) -> bool:
        return self.status in [self.Status.DELIVERED, self.Status.COMPLETED] and self.payment_status == self.PaymentStatus.PAID

    @property
    def is_paid(self) -> bool:
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def is_cod(self) -> bool:
        return self.payment_method == self.PaymentMethod.COD

    def confirm(self, admin_user=None) -> None:
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.PENDING:
            raise BusinessRuleViolation(message=f'Cannot confirm order in {self.get_status_display()} status')
        old_status = self.status
        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)

    def mark_processing(self, admin_user=None) -> None:
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status not in [self.Status.PENDING, self.Status.CONFIRMED]:
            raise BusinessRuleViolation(message=f'Cannot process order in {self.get_status_display()} status')
        old_status = self.status
        self.status = self.Status.PROCESSING
        if not self.confirmed_at:
            self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)

    def mark_as_paid(self, transaction_id: str = '', admin_user=None) -> None:
        old_payment_status = self.payment_status
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        if self.status == self.Status.PENDING:
            old_status = self.status
            self.status = self.Status.CONFIRMED
            self.confirmed_at = timezone.now()
            self.save(update_fields=['payment_status', 'paid_at', 'status', 'confirmed_at', 'updated_at'])
            self._log_status_change(old_status, self.status, admin_user, f'Payment received: {transaction_id}')
        else:
            self.save(update_fields=['payment_status', 'paid_at', 'updated_at'])

    def ship(self, tracking_code: str, provider: str = 'ghn', admin_user=None) -> None:
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status not in [self.Status.CONFIRMED, self.Status.PROCESSING, self.Status.READY_TO_SHIP]:
            raise BusinessRuleViolation(message=f'Cannot ship order in {self.get_status_display()} status')
        old_status = self.status
        self.status = self.Status.SHIPPING
        self.tracking_code = tracking_code
        self.shipping_provider = provider
        self.shipped_at = timezone.now()
        self.save(update_fields=['status', 'tracking_code', 'shipping_provider', 'shipped_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user, f'Tracking: {tracking_code}')

    def deliver(self, admin_user=None) -> None:
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.SHIPPING:
            raise BusinessRuleViolation(message=f'Cannot mark delivered in {self.get_status_display()} status')
        old_status = self.status
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        if self.is_cod:
            self.payment_status = self.PaymentStatus.PAID
            self.paid_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'payment_status', 'paid_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)

    def complete(self, admin_user=None) -> None:
        from apps.common.core.exceptions import BusinessRuleViolation
        if self.status != self.Status.DELIVERED:
            raise BusinessRuleViolation(message=f'Cannot complete order in {self.get_status_display()} status')
        old_status = self.status
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)

    def cancel(self, reason: str = '', cancelled_by=None) -> bool:
        if not self.can_cancel:
            return False
        old_status = self.status
        # Note: Stock release should be handled by signal or service layer
        # since we no longer have direct ForeignKey to Product
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason
        self.cancelled_by = cancelled_by
        self.save(update_fields=['status', 'cancelled_at', 'cancel_reason', 'cancelled_by', 'updated_at'])
        self._log_status_change(old_status, self.status, cancelled_by, reason)
        return True

    def refund(self, admin_user=None) -> None:
        old_status = self.status
        self.status = self.Status.REFUNDED
        self.payment_status = self.PaymentStatus.REFUNDED
        self.save(update_fields=['status', 'payment_status', 'updated_at'])
        self._log_status_change(old_status, self.status, admin_user)

    def _log_status_change(self, old_status: str, new_status: str, changed_by=None, notes: str = '') -> None:
        OrderStatusHistory.objects.create(order=self, old_status=old_status, new_status=new_status, changed_by=changed_by, notes=notes)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Order')
    # Using IntegerField instead of ForeignKey to avoid migration dependency on catalog
    product_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='Product ID')
    product_name = models.CharField(max_length=255, verbose_name='Product Name')
    product_sku = models.CharField(max_length=50, blank=True, verbose_name='SKU')
    product_image = models.URLField(blank=True, max_length=500, verbose_name='Image')
    product_attributes = models.JSONField(default=dict, blank=True, verbose_name='Attributes')
    quantity = models.PositiveIntegerField(verbose_name='Quantity')
    unit_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Unit Price')
    original_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Original Price')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Discount')
    returned_quantity = models.PositiveIntegerField(default=0, verbose_name='Returned Quantity')

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product_name}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def is_on_sale(self) -> bool:
        return self.original_price and self.original_price > self.unit_price


class OrderStatusHistory(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history', verbose_name='Order')
    old_status = models.CharField(max_length=20, choices=Order.Status.choices, verbose_name='Old Status')
    new_status = models.CharField(max_length=20, choices=Order.Status.choices, verbose_name='New Status')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Changed By')
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status History'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.old_status} → {self.new_status}"


class OrderNote(TimeStampedModel):
    class NoteType(models.TextChoices):
        GENERAL = 'general', 'General'
        PAYMENT = 'payment', 'Payment'
        SHIPPING = 'shipping', 'Shipping'
        CUSTOMER = 'customer', 'Customer'
        ISSUE = 'issue', 'Issue'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes', verbose_name='Order')
    note_type = models.CharField(max_length=20, choices=NoteType.choices, default=NoteType.GENERAL, verbose_name='Type')
    content = models.TextField(verbose_name='Content')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Created By')
    is_private = models.BooleanField(default=True, verbose_name='Private')

    class Meta:
        verbose_name = 'Order Note'
        verbose_name_plural = 'Order Notes'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Note for {self.order.order_number}"
