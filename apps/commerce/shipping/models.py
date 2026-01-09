"""Commerce Shipping - Shipping Models."""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class Shipment(UUIDModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PICKING = 'picking', 'Picking Up'
        PICKED_UP = 'picked_up', 'Picked Up'
        IN_TRANSIT = 'in_transit', 'In Transit'
        SORTING = 'sorting', 'Sorting'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed'
        WAITING_RETURN = 'waiting_return', 'Waiting Return'
        RETURNING = 'returning', 'Returning'
        RETURNED = 'returned', 'Returned'
        CANCELLED = 'cancelled', 'Cancelled'
        EXCEPTION = 'exception', 'Exception'

    class Provider(models.TextChoices):
        GHN = 'ghn', 'GHN'
        GHTK = 'ghtk', 'GHTK'
        VIETTEL_POST = 'vtp', 'Viettel Post'
        VNPOST = 'vnpost', 'VNPost'
        JNT = 'jnt', 'J&T Express'
        NINJA_VAN = 'ninjavan', 'Ninja Van'
        MANUAL = 'manual', 'Manual'

    order = models.OneToOneField('orders.Order', on_delete=models.PROTECT, related_name='shipment', verbose_name='Order')
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.GHN, db_index=True, verbose_name='Provider')
    tracking_code = models.CharField(max_length=100, unique=True, db_index=True, verbose_name='Tracking Code')
    provider_order_id = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='Provider Order ID')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name='Status')
    provider_status = models.CharField(max_length=50, blank=True, verbose_name='Provider Status')
    weight = models.PositiveIntegerField(default=500, verbose_name='Weight (g)')
    dimensions = models.JSONField(default=dict, blank=True, verbose_name='Dimensions')
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Shipping Fee')
    insurance_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Insurance Fee')
    cod_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='COD Fee')
    total_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Total Fee')
    cod_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='COD Amount')
    cod_collected = models.BooleanField(default=False, verbose_name='COD Collected')
    cod_transferred = models.BooleanField(default=False, verbose_name='COD Transferred')
    cod_transfer_date = models.DateField(null=True, blank=True, verbose_name='COD Transfer Date')
    provider_data = models.JSONField(default=dict, blank=True, verbose_name='Provider Data')
    service_id = models.IntegerField(null=True, blank=True, verbose_name='Service ID')
    service_type = models.CharField(max_length=50, blank=True, verbose_name='Service Type')
    expected_delivery = models.DateTimeField(null=True, blank=True, verbose_name='Expected Delivery')
    delivery_attempts = models.PositiveIntegerField(default=0, verbose_name='Delivery Attempts')
    max_delivery_attempts = models.PositiveIntegerField(default=3, verbose_name='Max Attempts')
    required_note = models.CharField(max_length=50, default='CHOTHUHANG', verbose_name='Required Note')
    note = models.TextField(blank=True, verbose_name='Note')
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name='Picked Up At')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='Delivered At')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='Returned At')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Cancelled At')
    last_location = models.CharField(max_length=255, blank=True, verbose_name='Last Location')
    last_status_update = models.DateTimeField(null=True, blank=True, verbose_name='Last Update')
    fail_reason = models.TextField(blank=True, verbose_name='Fail Reason')
    cancel_reason = models.TextField(blank=True, verbose_name='Cancel Reason')

    class Meta:
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['order', 'status']), models.Index(fields=['provider', 'status']), models.Index(fields=['status', '-created_at'])]

    def __str__(self) -> str:
        return f"Shipment {self.tracking_code}"

    def save(self, *args, **kwargs):
        if not self.total_fee:
            self.total_fee = self.shipping_fee + self.insurance_fee + self.cod_fee
        super().save(*args, **kwargs)

    @property
    def is_delivered(self) -> bool:
        return self.status == self.Status.DELIVERED

    @property
    def is_failed(self) -> bool:
        return self.status in [self.Status.FAILED, self.Status.EXCEPTION]

    @property
    def is_returned(self) -> bool:
        return self.status in [self.Status.WAITING_RETURN, self.Status.RETURNING, self.Status.RETURNED]

    @property
    def is_active(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.PICKING, self.Status.PICKED_UP, self.Status.IN_TRANSIT, self.Status.SORTING, self.Status.OUT_FOR_DELIVERY]

    @property
    def is_final(self) -> bool:
        return self.status in [self.Status.DELIVERED, self.Status.RETURNED, self.Status.CANCELLED]

    @property
    def can_cancel(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.PICKING]

    @property
    def can_retry(self) -> bool:
        return self.status == self.Status.FAILED and self.delivery_attempts < self.max_delivery_attempts

    @property
    def days_in_transit(self) -> int:
        if self.picked_up_at:
            if self.delivered_at:
                delta = self.delivered_at - self.picked_up_at
            else:
                delta = timezone.now() - self.picked_up_at
            return delta.days
        return 0

    @property
    def tracking_url(self) -> str:
        urls = {'ghn': f'https://donhang.ghn.vn/?order_code={self.tracking_code}', 'ghtk': f'https://i.ghtk.vn/{self.tracking_code}', 'vtp': f'https://viettelpost.vn/tra-cuu?code={self.tracking_code}'}
        return urls.get(self.provider, '')

    def update_status(self, new_status: str, provider_status: str = '', location: str = '', description: str = '', timestamp=None) -> 'ShipmentEvent':
        old_status = self.status
        self.status = new_status
        self.provider_status = provider_status or new_status
        self.last_location = location
        self.last_status_update = timestamp or timezone.now()
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
        event = ShipmentEvent.objects.create(shipment=self, status=provider_status or new_status, description=description or f"Status: {new_status}", location=location, occurred_at=now)
        return event

    def mark_delivered(self, timestamp=None) -> None:
        self.update_status(self.Status.DELIVERED, description='Delivered successfully', timestamp=timestamp)

    def mark_failed(self, reason: str, timestamp=None) -> None:
        self.fail_reason = reason
        self.update_status(self.Status.FAILED, description=f'Delivery failed: {reason}', timestamp=timestamp)

    def mark_returned(self, reason: str = '', timestamp=None) -> None:
        self.update_status(self.Status.RETURNED, description=f'Returned{": " + reason if reason else ""}', timestamp=timestamp)

    def cancel(self, reason: str = '') -> bool:
        if not self.can_cancel:
            return False
        self.cancel_reason = reason
        self.update_status(self.Status.CANCELLED, description=f'Cancelled{": " + reason if reason else ""}')
        return True


class ShipmentEvent(TimeStampedModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='events', verbose_name='Shipment')
    status = models.CharField(max_length=50, db_index=True, verbose_name='Status')
    description = models.TextField(verbose_name='Description')
    location = models.CharField(max_length=255, blank=True, verbose_name='Location')
    occurred_at = models.DateTimeField(db_index=True, verbose_name='Occurred At')
    provider_data = models.JSONField(default=dict, blank=True, verbose_name='Provider Data')

    class Meta:
        verbose_name = 'Shipment Event'
        verbose_name_plural = 'Shipment Events'
        ordering = ['-occurred_at']
        indexes = [models.Index(fields=['shipment', '-occurred_at'])]

    def __str__(self) -> str:
        return f"{self.shipment.tracking_code}: {self.status}"


class DeliveryAttempt(TimeStampedModel):
    class FailReason(models.TextChoices):
        NOT_HOME = 'not_home', 'No One Home'
        WRONG_ADDRESS = 'wrong_address', 'Wrong Address'
        PHONE_UNREACHABLE = 'phone_unreachable', 'Phone Unreachable'
        REFUSED = 'refused', 'Refused'
        INSUFFICIENT_COD = 'insufficient_cod', 'Insufficient COD'
        RESCHEDULED = 'rescheduled', 'Rescheduled'
        WEATHER = 'weather', 'Bad Weather'
        OTHER = 'other', 'Other'

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='attempt_logs', verbose_name='Shipment')
    attempt_number = models.PositiveIntegerField(verbose_name='Attempt #')
    attempted_at = models.DateTimeField(verbose_name='Attempted At')
    fail_reason = models.CharField(max_length=20, choices=FailReason.choices, verbose_name='Fail Reason')
    notes = models.TextField(blank=True, verbose_name='Notes')
    rescheduled_to = models.DateTimeField(null=True, blank=True, verbose_name='Rescheduled To')

    class Meta:
        verbose_name = 'Delivery Attempt'
        verbose_name_plural = 'Delivery Attempts'
        ordering = ['shipment', 'attempt_number']
        unique_together = ['shipment', 'attempt_number']

    def __str__(self) -> str:
        return f"{self.shipment.tracking_code} - Attempt #{self.attempt_number}"


class CODReconciliation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        TRANSFERRED = 'transferred', 'Transferred'
        DISPUTED = 'disputed', 'Disputed'

    provider = models.CharField(max_length=20, choices=Shipment.Provider.choices, verbose_name='Provider')
    reconciliation_date = models.DateField(db_index=True, verbose_name='Date')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Status')
    total_orders = models.PositiveIntegerField(default=0, verbose_name='Total Orders')
    total_cod = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Total COD')
    total_shipping_fee = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Total Shipping')
    net_amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Net Amount')
    transferred_at = models.DateTimeField(null=True, blank=True, verbose_name='Transferred At')
    transfer_reference = models.CharField(max_length=100, blank=True, verbose_name='Transfer Reference')
    notes = models.TextField(blank=True, verbose_name='Notes')
    shipments = models.ManyToManyField(Shipment, related_name='cod_reconciliations', blank=True, verbose_name='Shipments')

    class Meta:
        verbose_name = 'COD Reconciliation'
        verbose_name_plural = 'COD Reconciliations'
        ordering = ['-reconciliation_date']
        unique_together = ['provider', 'reconciliation_date']

    def __str__(self) -> str:
        return f"{self.get_provider_display()} - {self.reconciliation_date}"
