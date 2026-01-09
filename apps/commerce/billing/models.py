"""Commerce Billing - Payment Transaction Models."""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.core.models import UUIDModel, TimeStampedModel


class PaymentTransaction(UUIDModel):
    """Record of all payment attempts and transactions.
    
    Tracks the complete lifecycle of a payment from initiation to completion.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        EXPIRED = 'expired', 'Expired'
    
    class Gateway(models.TextChoices):
        COD = 'cod', 'Cash on Delivery'
        VNPAY = 'vnpay', 'VNPay'
        MOMO = 'momo', 'MoMo'
        STRIPE = 'stripe', 'Stripe'
    
    # Relationships
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        verbose_name='Order'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payment_transactions',
        verbose_name='User'
    )
    
    # Transaction Details
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Transaction ID'
    )
    gateway = models.CharField(
        max_length=20,
        choices=Gateway.choices,
        db_index=True,
        verbose_name='Payment Gateway'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Status'
    )
    
    # Amounts
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name='Amount'
    )
    currency = models.CharField(
        max_length=3,
        default='VND',
        verbose_name='Currency'
    )
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Transaction Fee'
    )
    
    # Gateway Reference
    gateway_transaction_id = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        verbose_name='Gateway Txn ID'
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Gateway Response'
    )
    
    # Payment URL (for redirect gateways)
    payment_url = models.URLField(
        max_length=2000,
        blank=True,
        verbose_name='Payment URL'
    )
    return_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Return URL'
    )
    
    # Timestamps
    initiated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Initiated At'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completed At'
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Expires At'
    )
    
    # Error Tracking
    error_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Error Code'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP Address'
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )
    
    class Meta:
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['gateway', 'status']),
            models.Index(fields=['gateway_transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self._generate_transaction_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def _generate_transaction_id():
        """Generate unique transaction ID."""
        import time
        import secrets
        timestamp = str(int(time.time()))[-8:]
        random_part = secrets.token_hex(4).upper()
        return f"TXN{timestamp}{random_part}"
    
    @property
    def is_successful(self):
        return self.status == self.Status.COMPLETED
    
    @property
    def is_pending(self):
        return self.status in [self.Status.PENDING, self.Status.PROCESSING]
    
    @property
    def is_expired(self):
        if self.expires_at and self.status == self.Status.PENDING:
            return timezone.now() > self.expires_at
        return False
    
    def mark_completed(self, gateway_txn_id: str = '', response: dict = None):
        """Mark transaction as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if gateway_txn_id:
            self.gateway_transaction_id = gateway_txn_id
        if response:
            self.gateway_response = response
        self.save(update_fields=[
            'status', 'completed_at', 'gateway_transaction_id',
            'gateway_response', 'updated_at'
        ])
        
        # Update order payment status
        self.order.mark_as_paid(transaction_id=self.transaction_id)
    
    def mark_failed(self, error_code: str = '', error_message: str = '', response: dict = None):
        """Mark transaction as failed."""
        self.status = self.Status.FAILED
        self.error_code = error_code
        self.error_message = error_message
        if response:
            self.gateway_response = response
        self.save(update_fields=[
            'status', 'error_code', 'error_message',
            'gateway_response', 'updated_at'
        ])


class PaymentRefund(UUIDModel):
    """Record of payment refunds."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    class Reason(models.TextChoices):
        CUSTOMER_REQUEST = 'customer_request', 'Customer Request'
        DUPLICATE = 'duplicate', 'Duplicate Payment'
        FRAUDULENT = 'fraudulent', 'Fraudulent'
        ORDER_CANCELLED = 'order_cancelled', 'Order Cancelled'
        PRODUCT_ISSUE = 'product_issue', 'Product Issue'
        OTHER = 'other', 'Other'
    
    # Relationships
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name='Original Transaction'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name='Order'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Processed By'
    )
    
    # Refund Details
    refund_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Refund ID'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Status'
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        default=Reason.CUSTOMER_REQUEST,
        verbose_name='Reason'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Notes'
    )
    
    # Amounts
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name='Refund Amount'
    )
    is_partial = models.BooleanField(
        default=False,
        verbose_name='Partial Refund'
    )
    
    # Gateway Response
    gateway_refund_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Gateway Refund ID'
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Gateway Response'
    )
    
    # Timestamps
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Requested At'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completed At'
    )
    
    class Meta:
        verbose_name = 'Payment Refund'
        verbose_name_plural = 'Payment Refunds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Refund {self.refund_id}"
    
    def save(self, *args, **kwargs):
        if not self.refund_id:
            self.refund_id = self._generate_refund_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def _generate_refund_id():
        """Generate unique refund ID."""
        import time
        import secrets
        timestamp = str(int(time.time()))[-8:]
        random_part = secrets.token_hex(3).upper()
        return f"REF{timestamp}{random_part}"
    
    def mark_completed(self, gateway_refund_id: str = '', response: dict = None):
        """Mark refund as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if gateway_refund_id:
            self.gateway_refund_id = gateway_refund_id
        if response:
            self.gateway_response = response
        self.save(update_fields=[
            'status', 'completed_at', 'gateway_refund_id',
            'gateway_response', 'updated_at'
        ])
