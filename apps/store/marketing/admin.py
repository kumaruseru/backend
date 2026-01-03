"""
Store Marketing - Production-Ready Admin Configuration.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Coupon, CouponUsage, Banner, FlashSale, FlashSaleItem, Campaign


class CouponUsageInline(admin.TabularInline):
    """Inline for coupon usage history."""
    model = CouponUsage
    extra = 0
    readonly_fields = ['user', 'order_id', 'discount_amount', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """Admin for coupons."""
    
    list_display = [
        'code', 'name', 'discount_display',
        'usage_display', 'validity_badge', 'is_active'
    ]
    list_filter = ['discount_type', 'is_active', 'is_public', 'apply_to', 'valid_until']
    search_fields = ['code', 'name', 'description']
    list_editable = ['is_active']
    date_hierarchy = 'created_at'
    filter_horizontal = ['applicable_categories', 'applicable_products', 'applicable_brands', 'specific_users']
    inlines = [CouponUsageInline]
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('code', 'name', 'description')
        }),
        ('Giảm giá', {
            'fields': ('discount_type', 'discount_value', 'min_order_value', 'max_discount')
        }),
        ('Giới hạn sử dụng', {
            'fields': ('usage_limit', 'usage_limit_per_user', 'used_count')
        }),
        ('Thời gian hiệu lực', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Phạm vi áp dụng', {
            'fields': ('apply_to', 'applicable_categories', 'applicable_products', 'applicable_brands'),
            'classes': ('collapse',)
        }),
        ('Đối tượng', {
            'fields': ('first_order_only', 'specific_users'),
            'classes': ('collapse',)
        }),
        ('Trạng thái', {
            'fields': ('is_active', 'is_public')
        }),
    )
    
    readonly_fields = ['used_count']
    
    @admin.display(description='Giảm giá')
    def discount_display(self, obj):
        return obj.get_discount_display()
    
    @admin.display(description='Sử dụng')
    def usage_display(self, obj):
        if obj.usage_limit:
            return f"{obj.used_count}/{obj.usage_limit}"
        return f"{obj.used_count}/∞"
    
    @admin.display(description='Hiệu lực')
    def validity_badge(self, obj):
        if obj.is_expired:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 2px 8px; '
                'border-radius: 3px; font-size: 11px;">Hết hạn</span>'
            )
        elif obj.is_valid:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 8px; '
                'border-radius: 3px; font-size: 11px;">Còn hiệu lực</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">Chưa hiệu lực</span>'
        )


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """Admin for banners."""
    
    list_display = [
        'title', 'position', 'image_preview',
        'schedule_display', 'stats_display',
        'is_active', 'sort_order'
    ]
    list_filter = ['position', 'is_active', 'category']
    search_fields = ['title', 'subtitle']
    list_editable = ['is_active', 'sort_order']
    raw_id_fields = ['category']
    
    fieldsets = (
        ('Nội dung', {
            'fields': ('title', 'subtitle', 'image', 'image_mobile')
        }),
        ('Link', {
            'fields': ('link_url', 'link_text')
        }),
        ('Vị trí', {
            'fields': ('position', 'category', 'sort_order')
        }),
        ('Lịch hiển thị', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Thống kê', {
            'fields': ('view_count', 'click_count'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['view_count', 'click_count']
    
    @admin.display(description='Hình ảnh')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 40px; width: auto;"/>',
                obj.image.url
            )
        return '-'
    
    @admin.display(description='Lịch')
    def schedule_display(self, obj):
        if obj.start_date and obj.end_date:
            return f"{obj.start_date.strftime('%d/%m')} - {obj.end_date.strftime('%d/%m')}"
        return 'Không giới hạn'
    
    @admin.display(description='Stats')
    def stats_display(self, obj):
        return f"👁 {obj.view_count} | 👆 {obj.click_count} ({obj.click_rate}%)"


class FlashSaleItemInline(admin.TabularInline):
    """Inline for flash sale items."""
    model = FlashSaleItem
    extra = 1
    raw_id_fields = ['product']
    fields = ['product', 'flash_price', 'original_price', 'quantity_limit', 'quantity_sold', 'is_active']
    readonly_fields = ['quantity_sold']


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    """Admin for flash sales."""
    
    list_display = ['name', 'schedule_display', 'status_badge', 'items_count', 'is_active']
    list_filter = ['status', 'is_active', 'start_time']
    search_fields = ['name', 'description']
    inlines = [FlashSaleItemInline]
    
    fieldsets = (
        ('Thông tin', {
            'fields': ('name', 'description', 'banner_image')
        }),
        ('Thời gian', {
            'fields': ('start_time', 'end_time')
        }),
        ('Trạng thái', {
            'fields': ('status', 'is_active')
        }),
    )
    
    actions = ['activate', 'deactivate']
    
    @admin.display(description='Thời gian')
    def schedule_display(self, obj):
        return format_html(
            '{}<br>đến {}',
            obj.start_time.strftime('%d/%m %H:%M'),
            obj.end_time.strftime('%d/%m %H:%M')
        )
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'scheduled': '#17a2b8',
            'active': '#28a745',
            'ended': '#6c757d',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Số SP')
    def items_count(self, obj):
        return obj.items.count()
    
    @admin.action(description='Kích hoạt')
    def activate(self, request, queryset):
        queryset.update(is_active=True)
    
    @admin.action(description='Tắt')
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin for campaigns."""
    
    list_display = [
        'name', 'campaign_type', 'status_badge',
        'stats_display', 'revenue_display', 'created_at'
    ]
    list_filter = ['campaign_type', 'status', 'created_at']
    search_fields = ['name', 'description']
    raw_id_fields = ['coupon']
    
    fieldsets = (
        ('Thông tin', {
            'fields': ('name', 'description', 'campaign_type')
        }),
        ('Thời gian', {
            'fields': ('start_date', 'end_date', 'status')
        }),
        ('Đối tượng', {
            'fields': ('target_audience', 'coupon'),
            'classes': ('collapse',)
        }),
        ('Thống kê', {
            'fields': ('sent_count', 'open_count', 'click_count', 'conversion_count', 'revenue'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['sent_count', 'open_count', 'click_count', 'conversion_count', 'revenue']
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'scheduled': '#17a2b8',
            'active': '#28a745',
            'paused': '#ffc107',
            'completed': '#6f42c1',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Stats')
    def stats_display(self, obj):
        return f"📤 {obj.sent_count} | 📬 {obj.open_count} ({obj.open_rate}%) | 🖱 {obj.click_count}"
    
    @admin.display(description='Doanh thu')
    def revenue_display(self, obj):
        return f"{obj.revenue:,.0f}₫"
