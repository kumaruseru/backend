"""Store Wishlist - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Wishlist, WishlistItem


class WishlistItemInline(TabularInline):
    model = WishlistItem
    extra = 0
    readonly_fields = ['product', 'price_when_added', 'lowest_price_seen', 'created_at']
    fields = ['product', 'priority', 'notify_on_sale', 'target_price', 'price_when_added', 'lowest_price_seen', 'created_at']


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ['user_email', 'name', 'is_default', 'is_public', 'items_count', 'created_at']
    list_filter = ['is_default', 'is_public', 'created_at']
    search_fields = ['user__email', 'name']
    raw_id_fields = ['user']
    readonly_fields = ['share_token', 'created_at', 'updated_at']
    inlines = [WishlistItemInline]

    fieldsets = (
        ('Info', {'fields': ('user', 'name', 'description')}),
        ('Settings', {'fields': ('is_default', 'is_public', 'share_token')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Items')
    def items_count(self, obj):
        return obj.items.count()


@admin.register(WishlistItem)
class WishlistItemAdmin(ModelAdmin):
    list_display = ['product_name', 'wishlist_name', 'priority_badge', 'price_info', 'notify_on_sale', 'created_at']
    list_filter = ['priority', 'notify_on_sale', 'created_at']
    search_fields = ['product__name', 'wishlist__user__email']
    raw_id_fields = ['wishlist', 'product']
    readonly_fields = ['price_when_added', 'lowest_price_seen', 'last_price_alert_at', 'created_at', 'updated_at']

    fieldsets = (
        ('Item', {'fields': ('wishlist', 'product', 'note')}),
        ('Settings', {'fields': ('priority', 'notify_on_sale', 'target_price')}),
        ('Price Tracking', {'fields': ('price_when_added', 'lowest_price_seen', 'last_price_alert_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Product')
    def product_name(self, obj):
        return obj.product.name[:40]

    @admin.display(description='Wishlist')
    def wishlist_name(self, obj):
        return f"{obj.wishlist.user.email} - {obj.wishlist.name}"

    @admin.display(description='Priority')
    def priority_badge(self, obj):
        colors = {'high': '#dc3545', 'medium': '#ffc107', 'low': '#6c757d'}
        color = colors.get(obj.priority, '#6c757d')
        text_color = 'white' if obj.priority == 'high' else 'black'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, text_color, obj.get_priority_display())

    @admin.display(description='Price')
    def price_info(self, obj):
        if obj.price_when_added:
            return f"{obj.price_when_added:,.0f}₫"
        return '-'
