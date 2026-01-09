"""Commerce Orders - Serializers."""
from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from .models import Order, OrderItem, OrderStatusHistory, OrderNote


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_sku', 'product_image', 'product_attributes', 'quantity', 'unit_price', 'original_price', 'discount_amount', 'subtotal', 'is_on_sale', 'returned_quantity']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    old_status_display = serializers.CharField(source='get_old_status_display', read_only=True)
    new_status_display = serializers.CharField(source='get_new_status_display', read_only=True)
    changed_by_email = serializers.CharField(source='changed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'old_status', 'old_status_display', 'new_status', 'new_status_display', 'changed_by_email', 'notes', 'created_at']


class OrderNoteSerializer(serializers.ModelSerializer):
    note_type_display = serializers.CharField(source='get_note_type_display', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)

    class Meta:
        model = OrderNote
        fields = ['id', 'note_type', 'note_type_display', 'content', 'created_by_email', 'is_private', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    full_address = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    can_refund = serializers.ReadOnlyField()
    is_paid = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'user', 'user_email', 'status', 'status_display', 'source', 'recipient_name', 'phone', 'email', 'address', 'ward', 'district', 'city', 'full_address', 'payment_method', 'payment_method_display', 'payment_status', 'payment_status_display', 'subtotal', 'shipping_fee', 'discount', 'coupon_discount', 'tax', 'total', 'currency', 'coupon_code', 'tracking_code', 'shipping_provider', 'customer_note', 'is_priority', 'is_gift', 'gift_message', 'confirmed_at', 'paid_at', 'shipped_at', 'delivered_at', 'completed_at', 'cancelled_at', 'cancel_reason', 'items', 'status_history', 'item_count', 'can_cancel', 'can_refund', 'is_paid', 'created_at', 'updated_at']


class OrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    item_count = serializers.ReadOnlyField()
    first_item_image = serializers.SerializerMethodField()
    first_item_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'status_display', 'payment_status', 'payment_status_display', 'total', 'item_count', 'first_item_image', 'first_item_name', 'tracking_code', 'created_at']

    def get_first_item_image(self, obj) -> str:
        first = obj.items.first()
        return first.product_image if first else ''

    def get_first_item_name(self, obj) -> str:
        first = obj.items.first()
        return first.product_name if first else ''


class OrderTrackingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['order_number', 'status', 'status_display', 'tracking_code', 'shipping_provider', 'shipped_at', 'delivered_at', 'status_history']


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(min_value=1, default=1)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, min_length=1)
    recipient_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    address = serializers.CharField(max_length=255)
    ward = serializers.CharField(max_length=100)
    district = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    district_id = serializers.IntegerField(required=False, allow_null=True)
    ward_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices, default=Order.PaymentMethod.COD)
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=50)
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    is_gift = serializers.BooleanField(default=False)
    gift_message = serializers.CharField(required=False, allow_blank=True, max_length=500)
    source = serializers.ChoiceField(choices=Order.Source.choices, default=Order.Source.WEB)


class OrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class OrderNoteCreateSerializer(serializers.Serializer):
    note_type = serializers.ChoiceField(choices=OrderNote.NoteType.choices, default=OrderNote.NoteType.GENERAL)
    content = serializers.CharField(min_length=1, max_length=2000)
    is_private = serializers.BooleanField(default=True)


class AdminOrderUpdateSerializer(serializers.Serializer):
    admin_note = serializers.CharField(required=False, allow_blank=True)
    is_priority = serializers.BooleanField(required=False)
    tracking_code = serializers.CharField(required=False, allow_blank=True, max_length=100)
    shipping_provider = serializers.CharField(required=False, allow_blank=True, max_length=20)


class AdminBulkStatusUpdateSerializer(serializers.Serializer):
    order_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    status = serializers.ChoiceField(choices=[('confirmed', 'Confirmed'), ('processing', 'Processing'), ('ready_to_ship', 'Ready to Ship')])


class OrderStatisticsSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=0)
    avg_order_value = serializers.DecimalField(max_digits=12, decimal_places=0)
    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    processing = serializers.IntegerField()
    shipping = serializers.IntegerField()
    delivered = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    cancellation_rate = serializers.FloatField()
    paid_orders = serializers.IntegerField()
    unpaid_orders = serializers.IntegerField()
    cod_orders = serializers.IntegerField()
    online_payment_orders = serializers.IntegerField()
