"""Store Marketing - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign


class FlashSaleItemInline(TabularInline):
    model = FlashSaleItem
    extra = 0
    fields = ['product', 'flash_price', 'original_price', 'quantity_limit', 'quantity_sold', 'is_active', 'sort_order']
    readonly_fields = ['quantity_sold']
    raw_id_fields = ['product']


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ['code', 'name', 'discount_display', 'usage_display', 'status_badge', 'valid_until', 'is_active']
    list_filter = ['discount_type', 'apply_to', 'is_active', 'is_public', 'valid_from', 'valid_until']
    search_fields = ['code', 'name', 'description']
    filter_horizontal = ['applicable_categories', 'applicable_products', 'applicable_brands', 'specific_users']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic', {'fields': ('code', 'name', 'description')}),
        ('Discount', {'fields': ('discount_type', 'discount_value', 'min_order_value', 'max_discount')}),
        ('Usage Limits', {'fields': ('usage_limit', 'usage_limit_per_user', 'used_count')}),
        ('Validity', {'fields': ('valid_from', 'valid_until')}),
        ('Targeting', {'fields': ('apply_to', 'applicable_categories', 'applicable_products', 'applicable_brands'), 'classes': ('collapse',)}),
        ('User Targeting', {'fields': ('first_order_only', 'specific_users'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('is_active', 'is_public')}),
    )

    @admin.display(description='Discount')
    def discount_display(self, obj):
        return obj.get_discount_display()

    @admin.display(description='Usage')
    def usage_display(self, obj):
        if obj.usage_limit:
            return f"{obj.used_count}/{obj.usage_limit}"
        return f"{obj.used_count}/∞"

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.is_expired:
            return format_html('<span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 3px;">Expired</span>')
        elif obj.is_valid:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px;">Valid</span>')
        return format_html('<span style="background: #ffc107; color: black; padding: 2px 8px; border-radius: 3px;">Inactive</span>')


@admin.register(CouponUsage)
class CouponUsageAdmin(ModelAdmin):
    list_display = ['coupon', 'user', 'discount_amount', 'created_at']
    list_filter = ['coupon', 'created_at']
    search_fields = ['coupon__code', 'user__email']
    raw_id_fields = ['coupon', 'user']
    readonly_fields = ['created_at']


@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ['title', 'position', 'status_badge', 'stats_display', 'sort_order', 'is_active']
    list_filter = ['position', 'is_active', 'created_at']
    search_fields = ['title', 'subtitle']
    raw_id_fields = ['category']
    readonly_fields = ['view_count', 'click_count', 'created_at', 'updated_at']
    list_editable = ['sort_order', 'is_active']

    fieldsets = (
        ('Content', {'fields': ('title', 'subtitle', 'image', 'image_mobile')}),
        ('Link', {'fields': ('link_url', 'link_text')}),
        ('Targeting', {'fields': ('position', 'category')}),
        ('Schedule', {'fields': ('start_date', 'end_date')}),
        ('Settings', {'fields': ('is_active', 'sort_order')}),
        ('Stats', {'fields': ('view_count', 'click_count'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.is_scheduled_active:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px;">Active</span>')
        return format_html('<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 3px;">Inactive</span>')

    @admin.display(description='Stats')
    def stats_display(self, obj):
        return f"👁 {obj.view_count} | 🖱 {obj.click_count} ({obj.click_rate}%)"


@admin.register(FlashSale)
class FlashSaleAdmin(ModelAdmin):
    list_display = ['name', 'status_badge', 'start_time', 'end_time', 'items_count', 'is_active']
    list_filter = ['status', 'is_active', 'start_time']
    search_fields = ['name', 'description']
    readonly_fields = ['status', 'created_at', 'updated_at']
    inlines = [FlashSaleItemInline]

    fieldsets = (
        ('Info', {'fields': ('name', 'description', 'banner_image')}),
        ('Schedule', {'fields': ('start_time', 'end_time')}),
        ('Status', {'fields': ('status', 'is_active')}),
    )

    actions = ['activate_flash_sales', 'cancel_flash_sales']

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'scheduled': '#17a2b8', 'active': '#28a745', 'ended': '#6c757d', 'cancelled': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>', color, obj.get_status_display())

    @admin.display(description='Items')
    def items_count(self, obj):
        return obj.items.count()

    @admin.action(description='Activate selected')
    def activate_flash_sales(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Cancel selected')
    def cancel_flash_sales(self, request, queryset):
        queryset.update(status='cancelled', is_active=False)


@admin.register(Campaign)
class CampaignAdmin(ModelAdmin):
    list_display = ['name', 'campaign_type', 'status_badge', 'stats_display', 'created_at']
    list_filter = ['campaign_type', 'status', 'created_at']
    search_fields = ['name', 'description']
    raw_id_fields = ['coupon']
    readonly_fields = ['sent_count', 'open_count', 'click_count', 'conversion_count', 'revenue', 'created_at', 'updated_at']

    fieldsets = (
        ('Info', {'fields': ('name', 'description', 'campaign_type')}),
        ('Schedule', {'fields': ('start_date', 'end_date', 'status')}),
        ('Targeting', {'fields': ('target_audience', 'coupon'), 'classes': ('collapse',)}),
        ('Stats', {'fields': ('sent_count', 'open_count', 'click_count', 'conversion_count', 'revenue'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'draft': '#6c757d', 'scheduled': '#17a2b8', 'active': '#28a745', 'paused': '#ffc107', 'completed': '#28a745'}
        color = colors.get(obj.status, '#6c757d')
        text_color = 'black' if obj.status == 'paused' else 'white'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px;">{}</span>', color, text_color, obj.get_status_display())

    @admin.display(description='Stats')
    def stats_display(self, obj):
        return f"📧 {obj.sent_count} | 👁 {obj.open_rate}% | 🖱 {obj.click_rate}%"
