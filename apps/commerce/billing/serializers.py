"""
Commerce Billing - Production-Ready Serializers.

Comprehensive DTOs with nested logs, refunds,
and validation.
"""
from rest_framework import serializers
from .models import Payment, Refund, PaymentLog, PaymentMethod


# --- Output Serializers ---

class PaymentLogSerializer(serializers.ModelSerializer):
    """Payment log DTO."""
    
    class Meta:
        model = PaymentLog
        fields = ['id', 'event', 'old_status', 'new_status', 'notes', 'created_at']


class RefundSerializer(serializers.ModelSerializer):
    """Refund output DTO."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    refund_type_display = serializers.CharField(source='get_refund_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment', 'refund_type', 'refund_type_display',
            'amount', 'reason', 'reason_display', 'reason_detail',
            'status', 'status_display',
            'refund_id', 'processed_at',
            'created_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """Full payment output DTO."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    
    logs = PaymentLogSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    
    # Computed
    is_completed = serializers.ReadOnlyField()
    is_pending = serializers.ReadOnlyField()
    is_failed = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    can_retry = serializers.ReadOnlyField()
    can_refund = serializers.ReadOnlyField()
    refundable_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'user', 'user_email',
            'method', 'method_display', 'amount', 'currency',
            'status', 'status_display',
            'transaction_id', 'provider_transaction_id',
            'payment_url', 'qr_code_url',
            'failure_reason', 'failure_code',
            'retry_count', 'max_retries',
            'expires_at', 'paid_at',
            'refunded_amount', 'refundable_amount',
            'is_completed', 'is_pending', 'is_failed', 'is_expired',
            'can_retry', 'can_refund',
            'logs', 'refunds',
            'created_at', 'updated_at'
        ]


class PaymentListSerializer(serializers.ModelSerializer):
    """Simplified payment for listing."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order_number', 'method', 'method_display',
            'amount', 'status', 'status_display',
            'paid_at', 'created_at'
        ]


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Saved payment method DTO."""
    method_type_display = serializers.CharField(source='get_method_type_display', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'method_type', 'method_type_display', 'provider',
            'display_name', 'last_four', 'brand',
            'is_default', 'is_active', 'expires_at', 'is_expired',
            'created_at'
        ]
    
    def get_is_expired(self, obj) -> bool:
        from django.utils import timezone
        if obj.expires_at:
            return obj.expires_at < timezone.now().date()
        return False


# --- Input Serializers ---

class CreatePaymentSerializer(serializers.Serializer):
    """Create payment request."""
    order_id = serializers.UUIDField(required=True)
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.VNPAY
    )
    return_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)
    
    # Optional saved method
    payment_method_id = serializers.UUIDField(required=False)


class PaymentCallbackSerializer(serializers.Serializer):
    """Generic payment callback."""
    transaction_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    amount = serializers.IntegerField(required=False)
    order_info = serializers.CharField(required=False)
    
    # VNPay specific
    vnp_ResponseCode = serializers.CharField(required=False)
    vnp_TransactionNo = serializers.CharField(required=False)
    vnp_TxnRef = serializers.CharField(required=False)
    vnp_Amount = serializers.CharField(required=False)
    vnp_SecureHash = serializers.CharField(required=False)
    
    # MoMo specific
    resultCode = serializers.CharField(required=False)
    transId = serializers.CharField(required=False)
    orderId = serializers.CharField(required=False)
    signature = serializers.CharField(required=False)


class RefundRequestSerializer(serializers.Serializer):
    """Request refund input."""
    payment_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=0,
        required=False  # If not provided, full refund
    )
    reason = serializers.ChoiceField(
        choices=Refund.Reason.choices,
        default=Refund.Reason.CUSTOMER_REQUEST
    )
    reason_detail = serializers.CharField(required=False, allow_blank=True, max_length=500)


class SavePaymentMethodSerializer(serializers.Serializer):
    """Save payment method for future use."""
    method_type = serializers.ChoiceField(choices=PaymentMethod.Type.choices)
    provider = serializers.ChoiceField(choices=Payment.Method.choices)
    token = serializers.CharField()
    display_name = serializers.CharField(max_length=100)
    last_four = serializers.CharField(max_length=4, required=False)
    brand = serializers.CharField(max_length=30, required=False)
    expires_at = serializers.DateField(required=False)
    is_default = serializers.BooleanField(default=False)


# --- Response Serializers ---

class PaymentUrlResponseSerializer(serializers.Serializer):
    """Payment URL creation response."""
    payment_id = serializers.UUIDField()
    payment_url = serializers.URLField()
    qr_code_url = serializers.URLField(required=False)
    expires_at = serializers.DateTimeField()
    transaction_id = serializers.CharField()


class PaymentResultSerializer(serializers.Serializer):
    """Payment result response."""
    success = serializers.BooleanField()
    payment_id = serializers.UUIDField()
    order_number = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    transaction_id = serializers.CharField(required=False)
    redirect_url = serializers.URLField(required=False)


# --- Statistics ---

class PaymentStatisticsSerializer(serializers.Serializer):
    """Payment statistics output."""
    period_days = serializers.IntegerField()
    total_payments = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=0)
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    success_rate = serializers.FloatField()
    
    # By method
    by_method = serializers.DictField()
    
    # Refunds
    total_refunds = serializers.IntegerField()
    total_refunded = serializers.DecimalField(max_digits=15, decimal_places=0)
