"""Commerce Returns - Serializers."""
from rest_framework import serializers
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory


class ReturnItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='order_item.product_name', read_only=True)
    product_image = serializers.CharField(source='order_item.product_image', read_only=True)
    unit_price = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = ReturnItem
        fields = ['id', 'order_item', 'product_name', 'product_image', 'quantity', 'reason', 'condition', 'notes', 'accepted_quantity', 'refund_amount', 'unit_price', 'subtotal']


class ReturnImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnImage
        fields = ['id', 'image', 'caption', 'created_at']


class ReturnStatusHistorySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    changed_by_email = serializers.CharField(source='changed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = ReturnStatusHistory
        fields = ['id', 'status', 'status_display', 'changed_by_email', 'notes', 'created_at']


class ReturnRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    refund_method_display = serializers.CharField(source='get_refund_method_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    items = ReturnItemSerializer(many=True, read_only=True)
    images = ReturnImageSerializer(many=True, read_only=True)
    status_history = ReturnStatusHistorySerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    is_partial_return = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    days_since_delivery = serializers.ReadOnlyField()
    is_within_return_window = serializers.ReadOnlyField()

    class Meta:
        model = ReturnRequest
        fields = ['id', 'request_number', 'order', 'order_number', 'user', 'user_email', 'status', 'status_display', 'reason', 'reason_display', 'description', 'refund_method', 'refund_method_display', 'requested_refund', 'approved_refund', 'bank_name', 'bank_account_number', 'bank_account_name', 'return_tracking_code', 'return_carrier', 'admin_notes', 'rejection_reason', 'quality_check_passed', 'quality_check_notes', 'processed_at', 'received_at', 'refunded_at', 'completed_at', 'total_items', 'is_partial_return', 'can_cancel', 'days_since_delivery', 'is_within_return_window', 'items', 'images', 'status_history', 'created_at', 'updated_at']


class ReturnRequestListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    total_items = serializers.ReadOnlyField()

    class Meta:
        model = ReturnRequest
        fields = ['id', 'request_number', 'order_number', 'status', 'status_display', 'reason', 'reason_display', 'requested_refund', 'approved_refund', 'total_items', 'created_at']


class ReturnItemCreateSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    refund_amount = serializers.DecimalField(max_digits=12, decimal_places=0, default=0)


class ReturnCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=ReturnRequest.Reason.choices)
    description = serializers.CharField(min_length=10)
    refund_method = serializers.ChoiceField(choices=ReturnRequest.RefundMethod.choices, default='original')
    items = ReturnItemCreateSerializer(many=True, min_length=1)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    bank_account_number = serializers.CharField(required=False, allow_blank=True)
    bank_account_name = serializers.CharField(required=False, allow_blank=True)


class ReturnApproveSerializer(serializers.Serializer):
    approved_refund = serializers.DecimalField(max_digits=12, decimal_places=0)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReturnRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5)


class ReturnReceiveSerializer(serializers.Serializer):
    quality_passed = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)


class ReturnStatisticsSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    total_returns = serializers.IntegerField()
    pending = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    completed = serializers.IntegerField()
    total_refunded = serializers.DecimalField(max_digits=15, decimal_places=0)
    approval_rate = serializers.FloatField()
