"""Commerce Cart - Serializers."""
from rest_framework import serializers
from .models import Cart, CartItem, SavedForLater


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    subtotal = serializers.ReadOnlyField()
    savings = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    has_price_changed = serializers.ReadOnlyField()
    current_product_price = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ['id', 'product_id', 'product_name', 'product_image', 'quantity', 'unit_price', 'original_price', 'subtotal', 'savings', 'is_on_sale', 'has_price_changed', 'current_product_price', 'is_out_of_stock', 'available_quantity', 'selected_attributes', 'created_at']

    def get_product_image(self, obj) -> str:
        if obj.product.images.exists():
            return obj.product.images.first().image.url
        return ''


class SavedForLaterSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    current_price = serializers.ReadOnlyField()
    price_dropped = serializers.ReadOnlyField()

    class Meta:
        model = SavedForLater
        fields = ['id', 'product_id', 'product_name', 'product_image', 'price_when_saved', 'current_price', 'price_dropped', 'created_at']

    def get_product_image(self, obj) -> str:
        if obj.product.images.exists():
            return obj.product.images.first().image.url
        return ''


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    saved_items = SavedForLaterSerializer(many=True, read_only=True)
    is_empty = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()
    unique_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    total_savings = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()
    has_out_of_stock = serializers.ReadOnlyField()
    saved_items_count = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'is_empty', 'total_items', 'unique_items', 'subtotal', 'total_savings', 'coupon_code', 'coupon_discount', 'total', 'has_out_of_stock', 'saved_items_count', 'items', 'saved_items', 'last_activity_at', 'created_at']


class CartSummarySerializer(serializers.ModelSerializer):
    total_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ['id', 'total_items', 'subtotal', 'coupon_discount', 'total']


class AddItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


class ApplyCouponSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(max_length=50)


class CouponResultSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    discount = serializers.DecimalField(max_digits=12, decimal_places=0, required=False)
    coupon = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class ValidationResultSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    issues = serializers.ListField(child=serializers.DictField())
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=0)
    total = serializers.DecimalField(max_digits=12, decimal_places=0)


class CartStatisticsSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    total_carts = serializers.IntegerField()
    carts_with_items = serializers.IntegerField()
    completed_checkout = serializers.IntegerField()
    abandoned_carts = serializers.IntegerField()
    abandonment_rate = serializers.FloatField()
