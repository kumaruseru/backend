"""
Commerce Cart - Production-Ready Serializers.

Comprehensive DTOs with nested items, saved items,
price tracking, and validation.
"""
from rest_framework import serializers
from .models import Cart, CartItem, SavedForLater, CartEvent


# --- Output Serializers ---

class CartItemSerializer(serializers.ModelSerializer):
    """Cart item output DTO."""
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    product_available = serializers.BooleanField(source='product.is_active', read_only=True)
    
    # Computed
    subtotal = serializers.ReadOnlyField()
    savings = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    current_product_price = serializers.ReadOnlyField()
    has_price_changed = serializers.ReadOnlyField()
    price_difference = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    exceeds_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_id', 'product_name', 'product_slug',
            'product_image', 'product_available',
            'quantity', 'unit_price', 'original_price',
            'selected_attributes',
            'subtotal', 'savings', 'is_on_sale',
            'current_product_price', 'has_price_changed', 'price_difference',
            'is_out_of_stock', 'available_quantity', 'exceeds_stock',
            'created_at', 'updated_at'
        ]
    
    def get_product_image(self, obj) -> str:
        first_img = obj.product.images.first()
        if first_img:
            return first_img.image.url
        return ''


class SavedForLaterSerializer(serializers.ModelSerializer):
    """Saved for later item DTO."""
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    product_available = serializers.BooleanField(source='product.is_active', read_only=True)
    
    current_price = serializers.ReadOnlyField()
    price_dropped = serializers.ReadOnlyField()
    price_change = serializers.ReadOnlyField()
    
    class Meta:
        model = SavedForLater
        fields = [
            'id', 'product', 'product_id', 'product_name', 'product_slug',
            'product_image', 'product_available',
            'price_when_saved', 'current_price',
            'price_dropped', 'price_change',
            'created_at'
        ]
    
    def get_product_image(self, obj) -> str:
        first_img = obj.product.images.first()
        if first_img:
            return first_img.image.url
        return ''


class CartSerializer(serializers.ModelSerializer):
    """Full cart output DTO."""
    items = CartItemSerializer(many=True, read_only=True)
    saved_items = SavedForLaterSerializer(many=True, read_only=True)
    
    # Computed
    is_empty = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()
    unique_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    total_savings = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()
    has_out_of_stock = serializers.ReadOnlyField()
    has_price_changes = serializers.ReadOnlyField()
    saved_items_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'user',
            'coupon_code', 'coupon_discount',
            'items', 'saved_items',
            'is_empty', 'total_items', 'unique_items',
            'subtotal', 'total_savings', 'total',
            'has_out_of_stock', 'has_price_changes',
            'saved_items_count',
            'last_activity_at', 'created_at', 'updated_at'
        ]


class CartSummarySerializer(serializers.ModelSerializer):
    """Minimal cart for header/badge."""
    total_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    has_coupon = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'total_items', 'subtotal', 'coupon_discount', 'has_coupon']
    
    def get_has_coupon(self, obj) -> bool:
        return bool(obj.coupon_code)


# --- Input Serializers ---

class AddToCartSerializer(serializers.Serializer):
    """Add item to cart input."""
    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    attributes = serializers.DictField(required=False, default=dict)
    
    def validate_product_id(self, value):
        """Validate product exists and is active."""
        from apps.store.catalog.models import Product
        
        try:
            product = Product.objects.get(id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError('Sản phẩm không tồn tại hoặc đã ngừng bán')
        
        return value
    
    def validate(self, attrs):
        """Check stock availability."""
        from apps.store.catalog.models import Product
        
        product = Product.objects.get(id=attrs['product_id'])
        quantity = attrs.get('quantity', 1)
        
        if hasattr(product, 'stock'):
            available = product.stock.available_quantity
            if quantity > available:
                if available == 0:
                    raise serializers.ValidationError({
                        'quantity': 'Sản phẩm đã hết hàng'
                    })
                raise serializers.ValidationError({
                    'quantity': f'Chỉ còn {available} sản phẩm'
                })
        
        attrs['product'] = product
        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    """Update cart item quantity."""
    quantity = serializers.IntegerField(min_value=0)
    
    def validate_quantity(self, value):
        item = self.context.get('item')
        
        if value > 0 and item:
            if hasattr(item.product, 'stock'):
                available = item.product.stock.available_quantity
                if value > available:
                    raise serializers.ValidationError(
                        f'Chỉ còn {available} sản phẩm'
                    )
        
        return value


class ApplyCouponSerializer(serializers.Serializer):
    """Apply coupon to cart."""
    coupon_code = serializers.CharField(max_length=50)


class BulkAddSerializer(serializers.Serializer):
    """Add multiple items at once."""
    items = serializers.ListField(
        child=AddToCartSerializer(),
        min_length=1,
        max_length=20
    )


# --- Stock Validation Response ---

class StockIssueSerializer(serializers.Serializer):
    """Stock issue response."""
    item_id = serializers.IntegerField()
    product_name = serializers.CharField()
    issue = serializers.CharField()
    message = serializers.CharField()
    requested = serializers.IntegerField(required=False)
    available = serializers.IntegerField(required=False)


class CartValidationSerializer(serializers.Serializer):
    """Cart validation response."""
    valid = serializers.BooleanField()
    issues = StockIssueSerializer(many=True)


# --- Price Update Response ---

class PriceChangeSerializer(serializers.Serializer):
    """Price change info."""
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    old_price = serializers.DecimalField(max_digits=12, decimal_places=0)
    new_price = serializers.DecimalField(max_digits=12, decimal_places=0)


class RefreshPricesResponseSerializer(serializers.Serializer):
    """Refresh prices response."""
    updated_count = serializers.IntegerField()
    changes = PriceChangeSerializer(many=True)
