"""Commerce Cart - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Cart, CartItem, SavedForLater, CartEvent


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    fields = ['product', 'quantity', 'unit_price', 'original_price', 'subtotal_display']
    readonly_fields = ['subtotal_display']
    raw_id_fields = ['product']

    @admin.display(description='Subtotal')
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,.0f}₫"


class SavedForLaterInline(TabularInline):
    model = SavedForLater
    extra = 0
    fields = ['product', 'price_when_saved', 'current_price_display', 'price_dropped']
    readonly_fields = ['current_price_display', 'price_dropped']
    raw_id_fields = ['product']

    @admin.display(description='Current Price')
    def current_price_display(self, obj):
        return f"{obj.current_price:,.0f}₫"


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ['id', 'user_display', 'items_count', 'total_display', 'coupon_display', 'last_activity_at']
    list_filter = ['abandonment_email_sent', 'last_activity_at', 'created_at']
    search_fields = ['user__email', 'session_key', 'coupon_code']
    raw_id_fields = ['user']
    readonly_fields = ['session_key', 'last_activity_at', 'created_at', 'updated_at']
    date_hierarchy = 'last_activity_at'
    inlines = [CartItemInline, SavedForLaterInline]

    fieldsets = (
        ('Owner', {'fields': ('user', 'session_key', 'expires_at')}),
        ('Coupon', {'fields': ('coupon_code', 'coupon_discount')}),
        ('Analytics', {'fields': ('last_activity_at', 'abandonment_email_sent')}),
        ('UTM', {'fields': ('utm_source', 'utm_medium', 'utm_campaign'), 'classes': ('collapse',)}),
    )

    @admin.display(description='User')
    def user_display(self, obj):
        if obj.user:
            return obj.user.email
        return f"Guest: {obj.session_key[:15] if obj.session_key else 'N/A'}..."

    @admin.display(description='Items')
    def items_count(self, obj):
        return obj.total_items

    @admin.display(description='Total')
    def total_display(self, obj):
        return f"{obj.total:,.0f}₫"

    @admin.display(description='Coupon')
    def coupon_display(self, obj):
        if obj.coupon_code:
            return f"{obj.coupon_code} (-{obj.coupon_discount:,.0f}₫)"
        return '-'


@admin.register(CartEvent)
class CartEventAdmin(ModelAdmin):
    list_display = ['cart', 'event_type_badge', 'product', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['cart__user__email', 'product__name']
    raw_id_fields = ['cart', 'product']
    readonly_fields = ['cart', 'event_type', 'product', 'data', 'created_at']

    @admin.display(description='Event')
    def event_type_badge(self, obj):
        colors = {'add_item': '#28a745', 'update_qty': '#17a2b8', 'remove_item': '#dc3545', 'apply_coupon': '#6f42c1', 'save_later': '#fd7e14', 'checkout_start': '#17a2b8', 'checkout_done': '#28a745', 'abandoned': '#dc3545'}
        color = colors.get(obj.event_type, '#6c757d')
        return format_html('<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, obj.get_event_type_display())
