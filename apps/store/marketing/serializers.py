"""
Store Marketing - Production-Ready Serializers.
"""
from rest_framework import serializers
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign


# ==================== Coupon Serializers ====================

class CouponSerializer(serializers.ModelSerializer):
    """Coupon output DTO."""
    is_valid = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    remaining_uses = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()
    discount_display = serializers.CharField(source='get_discount_display', read_only=True)
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'name', 'description',
            'discount_type', 'discount_value', 'discount_display',
            'min_order_value', 'max_discount',
            'usage_limit', 'usage_limit_per_user', 'used_count',
            'valid_from', 'valid_until',
            'is_valid', 'is_expired', 'remaining_uses', 'days_until_expiry',
            'first_order_only', 'is_public'
        ]


class CouponSimpleSerializer(serializers.ModelSerializer):
    """Minimal coupon for display."""
    discount_display = serializers.CharField(source='get_discount_display', read_only=True)
    
    class Meta:
        model = Coupon
        fields = ['code', 'name', 'discount_display', 'min_order_value', 'valid_until']


class CouponApplySerializer(serializers.Serializer):
    """Apply coupon input."""
    code = serializers.CharField(max_length=50)
    order_total = serializers.DecimalField(max_digits=12, decimal_places=0)


class CouponResultSerializer(serializers.Serializer):
    """Coupon application result."""
    valid = serializers.BooleanField()
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=0)
    message = serializers.CharField()
    coupon = CouponSimpleSerializer(required=False)


class CouponUsageSerializer(serializers.ModelSerializer):
    """Coupon usage history."""
    coupon_code = serializers.CharField(source='coupon.code')
    
    class Meta:
        model = CouponUsage
        fields = ['id', 'coupon_code', 'order_id', 'discount_amount', 'created_at']


# ==================== Banner Serializers ====================

class BannerSerializer(serializers.ModelSerializer):
    """Banner output DTO."""
    is_scheduled_active = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'subtitle',
            'image', 'image_mobile',
            'link_url', 'link_text',
            'position', 'category',
            'start_date', 'end_date',
            'is_scheduled_active', 'sort_order',
            'view_count', 'click_count', 'click_rate'
        ]


class BannerSimpleSerializer(serializers.ModelSerializer):
    """Banner for frontend display."""
    
    class Meta:
        model = Banner
        fields = ['id', 'title', 'subtitle', 'image', 'image_mobile', 'link_url', 'link_text']


# ==================== Flash Sale Serializers ====================

class FlashSaleItemSerializer(serializers.ModelSerializer):
    """Flash sale item output."""
    product_id = serializers.UUIDField(source='product.id')
    product_name = serializers.CharField(source='product.name')
    product_image = serializers.SerializerMethodField()
    product_slug = serializers.CharField(source='product.slug')
    discount_percentage = serializers.ReadOnlyField()
    remaining_quantity = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    sold_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = FlashSaleItem
        fields = [
            'id', 'product_id', 'product_name', 'product_image', 'product_slug',
            'flash_price', 'original_price', 'discount_percentage',
            'quantity_limit', 'quantity_sold', 'remaining_quantity',
            'is_sold_out', 'sold_percentage', 'per_user_limit'
        ]
    
    def get_product_image(self, obj) -> str:
        return obj.product.primary_image_url


class FlashSaleSerializer(serializers.ModelSerializer):
    """Flash sale output DTO."""
    items = FlashSaleItemSerializer(many=True, read_only=True)
    is_ongoing = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    time_remaining = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = FlashSale
        fields = [
            'id', 'name', 'description', 'banner_image',
            'start_time', 'end_time',
            'status', 'status_display',
            'is_ongoing', 'is_upcoming', 'time_remaining',
            'items'
        ]


class FlashSaleListSerializer(serializers.ModelSerializer):
    """Flash sale list output."""
    items_count = serializers.SerializerMethodField()
    is_ongoing = serializers.ReadOnlyField()
    
    class Meta:
        model = FlashSale
        fields = ['id', 'name', 'banner_image', 'start_time', 'end_time', 'is_ongoing', 'items_count']
    
    def get_items_count(self, obj) -> int:
        return obj.items.filter(is_active=True).count()


# ==================== Campaign Serializers ====================

class CampaignSerializer(serializers.ModelSerializer):
    """Campaign output DTO."""
    type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()
    coupon = CouponSimpleSerializer(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'description',
            'campaign_type', 'type_display',
            'start_date', 'end_date',
            'status', 'status_display',
            'coupon',
            'sent_count', 'open_count', 'click_count', 'conversion_count',
            'open_rate', 'click_rate', 'conversion_rate',
            'revenue', 'created_at'
        ]


class CampaignListSerializer(serializers.ModelSerializer):
    """Campaign list output."""
    type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Campaign
        fields = ['id', 'name', 'campaign_type', 'type_display', 'status', 'status_display', 'created_at']


# ==================== Statistics Serializers ====================

class MarketingStatisticsSerializer(serializers.Serializer):
    """Marketing statistics output."""
    active_coupons = serializers.IntegerField()
    total_coupon_uses = serializers.IntegerField()
    total_discount_given = serializers.DecimalField(max_digits=15, decimal_places=0)
    active_banners = serializers.IntegerField()
    active_flash_sales = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
