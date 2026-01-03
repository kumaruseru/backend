"""
Store Wishlist - Production-Ready Serializers.
"""
from rest_framework import serializers
from .models import Wishlist, WishlistItem


# ==================== Wishlist Serializers ====================

class WishlistSerializer(serializers.ModelSerializer):
    """Wishlist output DTO."""
    items_count = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    share_url = serializers.ReadOnlyField()
    
    class Meta:
        model = Wishlist
        fields = [
            'id', 'name', 'description',
            'is_default', 'is_public',
            'items_count', 'total_value', 'share_url',
            'created_at', 'updated_at'
        ]


class WishlistSimpleSerializer(serializers.ModelSerializer):
    """Minimal wishlist for dropdown."""
    items_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'is_default', 'items_count']


class WishlistCreateSerializer(serializers.ModelSerializer):
    """Create wishlist input."""
    
    class Meta:
        model = Wishlist
        fields = ['name', 'description', 'is_public']


# ==================== Item Serializers ====================

class WishlistItemSerializer(serializers.ModelSerializer):
    """Wishlist item output DTO."""
    product_id = serializers.UUIDField(source='product.id')
    product_name = serializers.CharField(source='product.name')
    product_slug = serializers.CharField(source='product.slug')
    product_image = serializers.SerializerMethodField()
    
    current_price = serializers.ReadOnlyField()
    price_change = serializers.ReadOnlyField()
    price_change_percentage = serializers.ReadOnlyField()
    is_price_dropped = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    reached_target_price = serializers.ReadOnlyField()
    
    class Meta:
        model = WishlistItem
        fields = [
            'id', 'product_id', 'product_name', 'product_slug', 'product_image',
            'note', 'priority',
            'price_when_added', 'current_price', 'lowest_price_seen',
            'price_change', 'price_change_percentage',
            'is_price_dropped', 'is_on_sale', 'is_in_stock',
            'notify_on_sale', 'target_price', 'reached_target_price',
            'created_at'
        ]
    
    def get_product_image(self, obj) -> str:
        return obj.product.primary_image_url


class WishlistItemListSerializer(serializers.ModelSerializer):
    """Simplified item for listing."""
    product_name = serializers.CharField(source='product.name')
    product_image = serializers.SerializerMethodField()
    current_price = serializers.ReadOnlyField()
    is_price_dropped = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = WishlistItem
        fields = [
            'id', 'product_name', 'product_image',
            'current_price', 'price_when_added',
            'is_price_dropped', 'is_in_stock',
            'created_at'
        ]
    
    def get_product_image(self, obj) -> str:
        return obj.product.primary_image_url


class WishlistItemAddSerializer(serializers.Serializer):
    """Add item to wishlist."""
    product_id = serializers.UUIDField()
    wishlist_id = serializers.UUIDField(required=False)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['high', 'medium', 'low'],
        default='medium',
        required=False
    )
    notify_on_sale = serializers.BooleanField(default=True, required=False)
    target_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False)


class WishlistItemUpdateSerializer(serializers.Serializer):
    """Update item."""
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=['high', 'medium', 'low'], required=False)
    notify_on_sale = serializers.BooleanField(required=False)
    target_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, allow_null=True)


class WishlistItemMoveSerializer(serializers.Serializer):
    """Move item to another wishlist."""
    target_wishlist_id = serializers.UUIDField()


# ==================== Shared Wishlist ====================

class SharedWishlistSerializer(serializers.ModelSerializer):
    """Public shared wishlist view."""
    owner_name = serializers.SerializerMethodField()
    items = WishlistItemListSerializer(many=True, read_only=True)
    items_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Wishlist
        fields = [
            'name', 'description', 'owner_name',
            'items_count', 'items',
            'created_at'
        ]
    
    def get_owner_name(self, obj) -> str:
        name = obj.user.get_full_name()
        if name:
            parts = name.split()
            return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]
        return 'Anonymous'


# ==================== Bulk Operations ====================

class BulkAddSerializer(serializers.Serializer):
    """Bulk add products to wishlist."""
    product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    wishlist_id = serializers.UUIDField(required=False)


class BulkRemoveSerializer(serializers.Serializer):
    """Bulk remove items."""
    item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )


class MoveToCartSerializer(serializers.Serializer):
    """Move items to cart."""
    item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    all_items = serializers.BooleanField(default=False)
