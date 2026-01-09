"""Commerce Returns - Return Models."""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel
from apps.commerce.orders.models import Order, OrderItem


class ReturnRequest(UUIDModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWING = 'reviewing', 'Reviewing'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        AWAITING_RETURN = 'awaiting_return', 'Awaiting Return'
        RECEIVED = 'received', 'Received'
        PROCESSING_REFUND = 'processing_refund', 'Processing Refund'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    class Reason(models.TextChoices):
        DEFECTIVE = 'defective', 'Defective/Damaged'
        WRONG_ITEM = 'wrong_item', 'Wrong Item'
        NOT_AS_DESCRIBED = 'not_as_described', 'Not As Described'
        MISSING_PARTS = 'missing_parts', 'Missing Parts'
        SIZE_FIT = 'size_fit', 'Size/Fit Issue'
        CHANGED_MIND = 'changed_mind', 'Changed Mind'
        QUALITY = 'quality', 'Quality Issue'
        DAMAGED_SHIPPING = 'damaged_shipping', 'Damaged in Shipping'
        OTHER = 'other', 'Other'

    class RefundMethod(models.TextChoices):
        ORIGINAL = 'original', 'Original Payment Method'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        WALLET = 'wallet', 'E-Wallet'
        STORE_CREDIT = 'store_credit', 'Store Credit'

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='return_requests', verbose_name='Order')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='return_requests', verbose_name='Customer')
    request_number = models.CharField(max_length=20, unique=True, editable=False, db_index=True, verbose_name='Request Number')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True, verbose_name='Status')
    reason = models.CharField(max_length=20, choices=Reason.choices, verbose_name='Reason')
    description = models.TextField(verbose_name='Description')
    refund_method = models.CharField(max_length=20, choices=RefundMethod.choices, default=RefundMethod.ORIGINAL, verbose_name='Refund Method')
    requested_refund = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Requested Refund')
    approved_refund = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Approved Refund')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='Bank Name')
    bank_account_number = models.CharField(max_length=30, blank=True, verbose_name='Account Number')
    bank_account_name = models.CharField(max_length=100, blank=True, verbose_name='Account Name')
    return_tracking_code = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='Return Tracking')
    return_carrier = models.CharField(max_length=50, blank=True, verbose_name='Return Carrier')
    admin_notes = models.TextField(blank=True, verbose_name='Admin Notes')
    rejection_reason = models.TextField(blank=True, verbose_name='Rejection Reason')
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_returns', verbose_name='Processed By')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Processed At')
    quality_check_passed = models.BooleanField(null=True, verbose_name='Quality Check')
    quality_check_notes = models.TextField(blank=True, verbose_name='Quality Notes')
    received_at = models.DateTimeField(null=True, blank=True, verbose_name='Received At')
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='Refunded At')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')

    class Meta:
        verbose_name = 'Return Request'
        verbose_name_plural = 'Return Requests'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at']), models.Index(fields=['status', '-created_at']), models.Index(fields=['order', 'status'])]
        permissions = [('can_approve_returns', 'Can approve return requests'), ('can_process_refunds', 'Can process refunds')]

    def __str__(self) -> str:
        return f"Return {self.request_number} - {self.order.order_number}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self._generate_request_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_request_number() -> str:
        import time
        timestamp = str(int(time.time()))[-6:]
        unique_id = str(uuid.uuid4().int)[:4]
        return f"RET{timestamp}{unique_id}"

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def is_partial_return(self) -> bool:
        return self.items.count() < self.order.items.count()

    @property
    def can_cancel(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.REVIEWING]

    @property
    def can_approve(self) -> bool:
        return self.status in [self.Status.PENDING, self.Status.REVIEWING]

    @property
    def can_receive(self) -> bool:
        return self.status in [self.Status.APPROVED, self.Status.AWAITING_RETURN]

    @property
    def days_since_delivery(self) -> int:
        if self.order.delivered_at:
            return (timezone.now() - self.order.delivered_at).days
        return 0

    @property
    def is_within_return_window(self) -> bool:
        return self.days_since_delivery <= 7

    def start_review(self, admin_user) -> None:
        if self.status != self.Status.PENDING:
            return
        self.status = self.Status.REVIEWING
        self.processed_by = admin_user
        self.save(update_fields=['status', 'processed_by', 'updated_at'])
        self._log_status_change(self.Status.REVIEWING, admin_user)

    def approve(self, admin_user, approved_refund: Decimal, notes: str = '') -> None:
        if not self.can_approve:
            return
        self.status = self.Status.APPROVED
        self.approved_refund = approved_refund
        self.admin_notes = notes
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'approved_refund', 'admin_notes', 'processed_by', 'processed_at', 'updated_at'])
        self._log_status_change(self.Status.APPROVED, admin_user, notes)

    def reject(self, admin_user, reason: str) -> None:
        if not self.can_approve:
            return
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.approved_refund = 0
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'rejection_reason', 'approved_refund', 'processed_by', 'processed_at', 'updated_at'])
        self._log_status_change(self.Status.REJECTED, admin_user, reason)

    def mark_awaiting_return(self) -> None:
        if self.status != self.Status.APPROVED:
            return
        self.status = self.Status.AWAITING_RETURN
        self.save(update_fields=['status', 'updated_at'])
        self._log_status_change(self.Status.AWAITING_RETURN)

    def receive_items(self, admin_user, quality_passed: bool, notes: str = '') -> None:
        if not self.can_receive:
            return
        self.status = self.Status.RECEIVED
        self.quality_check_passed = quality_passed
        self.quality_check_notes = notes
        self.received_at = timezone.now()
        self.save(update_fields=['status', 'quality_check_passed', 'quality_check_notes', 'received_at', 'updated_at'])
        self._log_status_change(self.Status.RECEIVED, admin_user, notes)

    def complete(self, admin_user=None) -> None:
        if self.status not in [self.Status.RECEIVED, self.Status.PROCESSING_REFUND]:
            return
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
        self._log_status_change(self.Status.COMPLETED, admin_user)

    def cancel(self, user=None, reason: str = '') -> None:
        if not self.can_cancel:
            return
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
        self._log_status_change(self.Status.CANCELLED, user, reason)

    def _log_status_change(self, new_status: str, user=None, notes: str = '') -> None:
        ReturnStatusHistory.objects.create(return_request=self, status=new_status, changed_by=user, notes=notes)


class ReturnItem(TimeStampedModel):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items', verbose_name='Return Request')
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name='return_items', verbose_name='Order Item')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Quantity')
    reason = models.CharField(max_length=20, choices=ReturnRequest.Reason.choices, blank=True, verbose_name='Reason')
    condition = models.CharField(max_length=50, blank=True, verbose_name='Condition')
    notes = models.TextField(blank=True, verbose_name='Notes')
    accepted_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name='Accepted Qty')
    refund_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Refund Amount')

    class Meta:
        verbose_name = 'Return Item'
        verbose_name_plural = 'Return Items'
        unique_together = ['return_request', 'order_item']

    def __str__(self) -> str:
        return f"{self.quantity}x {self.order_item.product_name}"

    @property
    def unit_price(self) -> Decimal:
        return self.order_item.unit_price

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


class ReturnImage(TimeStampedModel):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='images', verbose_name='Return Request')
    image = models.ImageField(upload_to='returns/%Y/%m/', verbose_name='Image')
    caption = models.CharField(max_length=255, blank=True, verbose_name='Caption')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Uploaded By')

    class Meta:
        verbose_name = 'Return Image'
        verbose_name_plural = 'Return Images'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Image for {self.return_request.request_number}"


class ReturnStatusHistory(TimeStampedModel):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='status_history', verbose_name='Return Request')
    status = models.CharField(max_length=20, choices=ReturnRequest.Status.choices, verbose_name='Status')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Changed By')
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Status History'
        verbose_name_plural = 'Status History'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.return_request.request_number}: {self.status}"
