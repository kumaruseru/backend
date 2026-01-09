"""Store Marketing - Serializers."""
from rest_framework import serializers
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign


class CouponSerializer(serializers.ModelSerializer):
    discount_display = serializers.CharField(source='get_discount_display', read_only=True)
    is_valid = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    remaining_uses = serializers.ReadOnlyField()
    days_until_expiry = serializers.ReadOnlyField()

    class Meta:
        model = Coupon
        fields = ['id', 'code', 'name', 'description', 'discount_type', 'discount_value', 'discount_display', 'min_order_value', 'max_discount', 'valid_from', 'valid_until', 'is_valid', 'is_expired', 'remaining_uses', 'days_until_expiry', 'is_public']


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    order_total = serializers.DecimalField(max_digits=12, decimal_places=0)


class CouponValidateResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    discount = serializers.DecimalField(max_digits=12, decimal_places=0)
    discount_display = serializers.CharField()
    message = serializers.CharField(required=False, allow_blank=True)


class BannerSerializer(serializers.ModelSerializer):
    is_scheduled_active = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()

    class Meta:
        model = Banner
        fields = ['id', 'title', 'subtitle', 'image', 'image_mobile', 'link_url', 'link_text', 'position', 'is_scheduled_active', 'click_rate']


class FlashSaleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    discount_percentage = serializers.ReadOnlyField()
    remaining_quantity = serializers.ReadOnlyField()
    is_sold_out = serializers.ReadOnlyField()
    sold_percentage = serializers.ReadOnlyField()

    class Meta:
        model = FlashSaleItem
        fields = ['id', 'product_id', 'product_name', 'product_image', 'flash_price', 'original_price', 'discount_percentage', 'quantity_limit', 'quantity_sold', 'remaining_quantity', 'is_sold_out', 'sold_percentage', 'per_user_limit']

    def get_product_image(self, obj) -> str:
        if obj.product.images.exists():
            return obj.product.images.first().image.url
        return ''


class FlashSaleSerializer(serializers.ModelSerializer):
    items = FlashSaleItemSerializer(many=True, read_only=True)
    is_ongoing = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    time_remaining = serializers.ReadOnlyField()

    class Meta:
        model = FlashSale
        fields = ['id', 'name', 'description', 'banner_image', 'start_time', 'end_time', 'status', 'is_ongoing', 'is_upcoming', 'time_remaining', 'items']


class FlashSaleListSerializer(serializers.ModelSerializer):
    is_ongoing = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    time_remaining = serializers.ReadOnlyField()
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = FlashSale
        fields = ['id', 'name', 'banner_image', 'start_time', 'end_time', 'status', 'is_ongoing', 'is_upcoming', 'time_remaining', 'items_count']

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class CampaignSerializer(serializers.ModelSerializer):
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = ['id', 'name', 'description', 'campaign_type', 'start_date', 'end_date', 'status', 'sent_count', 'open_count', 'click_count', 'conversion_count', 'revenue', 'open_rate', 'click_rate', 'conversion_rate', 'created_at']


class MarketingStatisticsSerializer(serializers.Serializer):
    active_coupons = serializers.IntegerField()
    total_coupon_usages = serializers.IntegerField()
    active_banners = serializers.IntegerField()
    active_flash_sales = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    total_campaign_conversions = serializers.IntegerField()
