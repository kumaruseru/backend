"""Store Wishlist - Serializers."""
from rest_framework import serializers
from .models import Wishlist, WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
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
        fields = ['id', 'product_id', 'product_name', 'product_image', 'note', 'priority', 'price_when_added', 'lowest_price_seen', 'current_price', 'price_change', 'price_change_percentage', 'is_price_dropped', 'is_on_sale', 'is_in_stock', 'notify_on_sale', 'target_price', 'reached_target_price', 'created_at']

    def get_product_image(self, obj) -> str:
        if obj.product.images.exists():
            return obj.product.images.first().image.url
        return ''


class WishlistSerializer(serializers.ModelSerializer):
    items_count = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    share_url = serializers.ReadOnlyField()
    items = WishlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'description', 'is_default', 'is_public', 'share_token', 'share_url', 'items_count', 'total_value', 'items', 'created_at', 'updated_at']


class WishlistListSerializer(serializers.ModelSerializer):
    items_count = serializers.ReadOnlyField()

    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'description', 'is_default', 'is_public', 'items_count', 'created_at']


class WishlistCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    is_public = serializers.BooleanField(default=False)


class WishlistUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_public = serializers.BooleanField(required=False)


class WishlistItemAddSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    wishlist_id = serializers.UUIDField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    priority = serializers.ChoiceField(choices=['high', 'medium', 'low'], default='medium')
    notify_on_sale = serializers.BooleanField(default=True)
    target_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, allow_null=True)


class WishlistItemUpdateSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    priority = serializers.ChoiceField(choices=['high', 'medium', 'low'], required=False)
    notify_on_sale = serializers.BooleanField(required=False)
    target_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, allow_null=True)


class BulkAddSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=50)
    wishlist_id = serializers.UUIDField(required=False, allow_null=True)


class BulkRemoveSerializer(serializers.Serializer):
    item_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=50)


class ToggleSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
