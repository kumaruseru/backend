"""Commerce Billing - API Serializers."""
from rest_framework import serializers
from .models import PaymentTransaction, PaymentRefund


class CreatePaymentSerializer(serializers.Serializer):
    """Serializer for creating a payment."""
    order_id = serializers.UUIDField(required=True)
    gateway = serializers.ChoiceField(
        choices=['cod', 'momo', 'vnpay', 'stripe'],
        required=False,
        help_text='Payment gateway. Defaults to order payment method.'
    )
    return_url = serializers.URLField(required=True)
    cancel_url = serializers.URLField(required=False)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """Serializer for payment transactions."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gateway_display = serializers.CharField(source='get_gateway_display', read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'transaction_id', 'order_number',
            'gateway', 'gateway_display', 'status', 'status_display',
            'amount', 'currency', 'fee',
            'gateway_transaction_id', 'payment_url',
            'is_successful', 'initiated_at', 'completed_at',
            'error_code', 'error_message',
        ]
        read_only_fields = fields


class PaymentTransactionDetailSerializer(PaymentTransactionSerializer):
    """Detailed serializer including response data."""
    
    class Meta(PaymentTransactionSerializer.Meta):
        fields = PaymentTransactionSerializer.Meta.fields + [
            'gateway_response', 'metadata', 'ip_address',
        ]


class CreateRefundSerializer(serializers.Serializer):
    """Serializer for creating a refund."""
    order_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=0,
        required=False,
        help_text='Refund amount. Defaults to full refund.'
    )
    reason = serializers.ChoiceField(
        choices=[
            ('customer_request', 'Customer Request'),
            ('duplicate', 'Duplicate Payment'),
            ('fraudulent', 'Fraudulent'),
            ('order_cancelled', 'Order Cancelled'),
            ('product_issue', 'Product Issue'),
            ('other', 'Other'),
        ],
        default='customer_request'
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentRefundSerializer(serializers.ModelSerializer):
    """Serializer for payment refunds."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = PaymentRefund
        fields = [
            'id', 'refund_id', 'order_number',
            'status', 'status_display',
            'reason', 'reason_display', 'notes',
            'amount', 'is_partial',
            'gateway_refund_id',
            'requested_at', 'completed_at',
        ]
        read_only_fields = fields


class PaymentGatewaySerializer(serializers.Serializer):
    """Serializer for available payment gateways."""
    code = serializers.CharField()
    name = serializers.CharField()
    supports_refund = serializers.BooleanField()
