"""
Commerce Returns - Production-Ready Serializers.

Comprehensive DTOs with validation, nested serialization,
and support for partial returns and image uploads.
"""
from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from apps.commerce.orders.models import Order
from .models import ReturnRequest, ReturnItem, ReturnImage, ReturnStatusHistory


# --- Output Serializers ---

class ReturnImageSerializer(serializers.ModelSerializer):
    """Return image DTO."""
    uploaded_by_email = serializers.CharField(source='uploaded_by.email', read_only=True)
    
    class Meta:
        model = ReturnImage
        fields = ['id', 'image', 'caption', 'uploaded_by_email', 'created_at']


class ReturnItemSerializer(serializers.ModelSerializer):
    """Return item output DTO."""
    product_name = serializers.CharField(source='order_item.product_name', read_only=True)
    product_image = serializers.CharField(source='order_item.product_image', read_only=True)
    unit_price = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    original_quantity = serializers.IntegerField(source='order_item.quantity', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'order_item', 'product_name', 'product_image',
            'quantity', 'original_quantity', 'unit_price', 'subtotal',
            'reason', 'reason_display', 'condition', 'notes',
            'accepted_quantity', 'refund_amount'
        ]


class ReturnStatusHistorySerializer(serializers.ModelSerializer):
    """Status history DTO."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    changed_by_email = serializers.CharField(source='changed_by.email', read_only=True)
    
    class Meta:
        model = ReturnStatusHistory
        fields = ['id', 'status', 'status_display', 'changed_by_email', 'notes', 'created_at']


class ReturnRequestSerializer(serializers.ModelSerializer):
    """Full return request output DTO."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    refund_method_display = serializers.CharField(source='get_refund_method_display', read_only=True)
    processed_by_email = serializers.CharField(source='processed_by.email', read_only=True)
    
    items = ReturnItemSerializer(many=True, read_only=True)
    images = ReturnImageSerializer(many=True, read_only=True)
    status_history = ReturnStatusHistorySerializer(many=True, read_only=True)
    
    total_items = serializers.ReadOnlyField()
    is_partial_return = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    days_since_delivery = serializers.ReadOnlyField()
    
    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'request_number', 'order', 'order_number',
            'user_email', 'status', 'status_display',
            'reason', 'reason_display', 'description',
            'refund_method', 'refund_method_display',
            'requested_refund', 'approved_refund',
            'bank_name', 'bank_account_number', 'bank_account_name',
            'return_tracking_code', 'return_carrier',
            'admin_notes', 'rejection_reason',
            'processed_by_email', 'processed_at',
            'quality_check_passed', 'quality_check_notes',
            'received_at', 'refunded_at', 'completed_at',
            'items', 'images', 'status_history',
            'total_items', 'is_partial_return', 'can_cancel',
            'days_since_delivery',
            'created_at', 'updated_at'
        ]


class ReturnRequestListSerializer(serializers.ModelSerializer):
    """Simplified return request for listing."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    total_items = serializers.ReadOnlyField()
    first_item_image = serializers.SerializerMethodField()
    
    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'request_number', 'order_number',
            'status', 'status_display',
            'reason', 'reason_display',
            'requested_refund', 'approved_refund',
            'total_items', 'first_item_image',
            'created_at'
        ]
    
    def get_first_item_image(self, obj) -> str:
        first_item = obj.items.first()
        return first_item.order_item.product_image if first_item else ''


# --- Input Serializers ---

class ReturnItemCreateSerializer(serializers.Serializer):
    """Return item creation input."""
    order_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(
        choices=ReturnRequest.Reason.choices,
        required=False,
        allow_blank=True
    )
    condition = serializers.CharField(required=False, allow_blank=True, max_length=50)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ReturnRequestCreateSerializer(serializers.Serializer):
    """Create return request input."""
    order_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=ReturnRequest.Reason.choices)
    description = serializers.CharField(min_length=20, max_length=2000)
    refund_method = serializers.ChoiceField(
        choices=ReturnRequest.RefundMethod.choices,
        default=ReturnRequest.RefundMethod.ORIGINAL
    )
    
    # Items to return
    items = ReturnItemCreateSerializer(many=True, min_length=1)
    
    # Bank info (required if refund_method is bank_transfer)
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    bank_account_number = serializers.CharField(required=False, allow_blank=True, max_length=30)
    bank_account_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    
    def validate_order_id(self, value):
        """Validate order ownership and eligibility."""
        user = self.context.get('user')
        
        try:
            order = Order.objects.prefetch_related('items').get(id=value, user=user)
        except Order.DoesNotExist:
            raise serializers.ValidationError('Đơn hàng không tồn tại')
        
        # Must be delivered
        if order.status != Order.Status.DELIVERED:
            raise serializers.ValidationError('Chỉ có thể yêu cầu hoàn trả đơn hàng đã giao')
        
        # Check return window (7 days)
        if order.delivered_at:
            deadline = order.delivered_at + timedelta(days=7)
            if timezone.now() > deadline:
                raise serializers.ValidationError(
                    'Đã quá thời hạn yêu cầu hoàn trả (7 ngày sau khi nhận hàng)'
                )
        
        # Check pending returns
        pending_count = order.return_requests.filter(
            status__in=[
                ReturnRequest.Status.PENDING,
                ReturnRequest.Status.REVIEWING,
                ReturnRequest.Status.APPROVED,
                ReturnRequest.Status.AWAITING_RETURN
            ]
        ).count()
        
        if pending_count > 0:
            raise serializers.ValidationError('Đơn hàng đã có yêu cầu hoàn trả đang xử lý')
        
        return value
    
    def validate_items(self, value):
        """Validate items to return."""
        if not value:
            raise serializers.ValidationError('Phải chọn ít nhất một sản phẩm để hoàn trả')
        
        order_id = self.initial_data.get('order_id')
        if not order_id:
            return value
        
        try:
            order = Order.objects.prefetch_related('items').get(id=order_id)
        except Order.DoesNotExist:
            return value
        
        order_item_ids = {item.id for item in order.items.all()}
        
        for item in value:
            if item['order_item_id'] not in order_item_ids:
                raise serializers.ValidationError(
                    f"Sản phẩm {item['order_item_id']} không thuộc đơn hàng này"
                )
            
            # Check quantity
            order_item = order.items.get(id=item['order_item_id'])
            if item['quantity'] > order_item.quantity:
                raise serializers.ValidationError(
                    f"Số lượng trả ({item['quantity']}) vượt quá số lượng đã mua ({order_item.quantity})"
                )
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        refund_method = attrs.get('refund_method')
        
        if refund_method == ReturnRequest.RefundMethod.BANK_TRANSFER:
            if not attrs.get('bank_name'):
                raise serializers.ValidationError({
                    'bank_name': 'Vui lòng nhập tên ngân hàng'
                })
            if not attrs.get('bank_account_number'):
                raise serializers.ValidationError({
                    'bank_account_number': 'Vui lòng nhập số tài khoản'
                })
            if not attrs.get('bank_account_name'):
                raise serializers.ValidationError({
                    'bank_account_name': 'Vui lòng nhập tên chủ tài khoản'
                })
        
        return attrs


class ReturnImageUploadSerializer(serializers.Serializer):
    """Upload evidence image."""
    image = serializers.ImageField()
    caption = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    def validate_image(self, value):
        """Validate image size and type."""
        max_size = 5 * 1024 * 1024  # 5MB
        
        if value.size > max_size:
            raise serializers.ValidationError('Kích thước ảnh tối đa là 5MB')
        
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError('Chỉ hỗ trợ ảnh JPEG, PNG, WebP')
        
        return value


class ReturnTrackingUpdateSerializer(serializers.Serializer):
    """Update return tracking info."""
    tracking_code = serializers.CharField(max_length=100)
    carrier = serializers.CharField(max_length=50, default='GHN')


# --- Admin Serializers ---

class ReturnApproveSerializer(serializers.Serializer):
    """Admin approve return."""
    approved_refund = serializers.DecimalField(
        max_digits=12,
        decimal_places=0,
        min_value=0
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    
    def validate_approved_refund(self, value):
        """Ensure refund doesn't exceed requested amount."""
        return_request = self.context.get('return_request')
        if return_request and value > return_request.requested_refund:
            raise serializers.ValidationError(
                f'Số tiền duyệt không được vượt quá số tiền yêu cầu ({return_request.requested_refund:,.0f}₫)'
            )
        return value


class ReturnRejectSerializer(serializers.Serializer):
    """Admin reject return."""
    reason = serializers.CharField(min_length=10, max_length=1000)


class ReturnReceiveSerializer(serializers.Serializer):
    """Admin mark items received."""
    quality_passed = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    
    # Item-level acceptance (optional)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class ReturnProcessRefundSerializer(serializers.Serializer):
    """Process refund for approved return."""
    confirm = serializers.BooleanField()
    
    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError('Vui lòng xác nhận để tiến hành hoàn tiền')
        return value
