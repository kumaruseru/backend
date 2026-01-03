"""
Store Wishlist - Production-Ready Admin Configuration.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    """Inline for wishlist items."""
    model = WishlistItem
    extra = 0
    raw_id_fields = ['product']
    fields = ['product', 'priority', 'note', 'price_when_added', 'notify_on_sale', 'created_at']
    readonly_fields = ['price_when_added', 'created_at']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Admin for wishlists."""
    
    list_display = ['name', 'user_email', 'items_count', 'is_default', 'is_public_badge', 'created_at']
    list_filter = ['is_default', 'is_public', 'created_at']
    search_fields = ['name', 'user__email']
    raw_id_fields = ['user']
    readonly_fields = ['share_token', 'created_at', 'updated_at']
    inlines = [WishlistItemInline]
    
    @admin.display(description='Người dùng')
    def user_email(self, obj):
        return obj.user.email
    
    @admin.display(description='Số item')
    def items_count(self, obj):
        return obj.items.count()
    
    @admin.display(description='Công khai')
    def is_public_badge(self, obj):
        if obj.is_public:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px;">Có</span>'
            )
        return '-'


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    """Admin for wishlist items."""
    
    list_display = [
        'product_name', 'user_email', 'wishlist_name',
        'priority_badge', 'price_display', 'notify_on_sale', 'created_at'
    ]
    list_filter = ['priority', 'notify_on_sale', 'created_at']
    search_fields = ['wishlist__user__email', 'product__name']
    raw_id_fields = ['wishlist', 'product']
    readonly_fields = ['price_when_added', 'lowest_price_seen', 'last_price_alert_at', 'created_at']
    
    @admin.display(description='Sản phẩm')
    def product_name(self, obj):
        return obj.product.name[:30]
    
    @admin.display(description='Người dùng')
    def user_email(self, obj):
        return obj.wishlist.user.email
    
    @admin.display(description='Danh sách')
    def wishlist_name(self, obj):
        return obj.wishlist.name
    
    @admin.display(description='Ưu tiên')
    def priority_badge(self, obj):
        colors = {
            'high': '#dc3545',
            'medium': '#ffc107',
            'low': '#6c757d',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            color, obj.get_priority_display()
        )
    
    @admin.display(description='Giá')
    def price_display(self, obj):
        current = obj.current_price
        if obj.is_price_dropped:
            return format_html(
                '<span style="color: green;">{:,.0f}₫</span> '
                '<small style="color: #666;">(giảm {}%)</small>',
                current, abs(obj.price_change_percentage)
            )
        return f"{current:,.0f}₫"
