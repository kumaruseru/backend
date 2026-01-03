"""
Commerce Cart - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Cart overview
- Inline items and saved items
- Cart value display
- Cleanup actions
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Cart, CartItem, SavedForLater, CartEvent


class CartItemInline(admin.TabularInline):
    """Inline for cart items."""
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'unit_price', 'subtotal_display', 'stock_status']
    fields = [
        'product', 'quantity', 'unit_price', 'original_price',
        'subtotal_display', 'stock_status'
    ]
    
    @admin.display(description='Thành tiền')
    def subtotal_display(self, obj):
        if obj.unit_price is None:
            return '-'
        return f"{obj.subtotal:,.0f}₫"
    
    @admin.display(description='Tồn kho')
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="color: red;">Hết hàng</span>')
        elif obj.exceeds_stock:
            return format_html(
                '<span style="color: orange;">Vượt quá (còn {})</span>',
                obj.available_quantity
            )
        return format_html('<span style="color: green;">OK</span>')


class SavedForLaterInline(admin.TabularInline):
    """Inline for saved items."""
    model = SavedForLater
    extra = 0
    readonly_fields = ['product', 'price_when_saved', 'current_price_display', 'price_status']
    fields = ['product', 'price_when_saved', 'current_price_display', 'price_status']
    
    @admin.display(description='Giá hiện tại')
    def current_price_display(self, obj):
        return f"{obj.current_price:,.0f}₫"
    
    @admin.display(description='Trạng thái')
    def price_status(self, obj):
        if obj.price_dropped:
            return format_html(
                '<span style="color: green;">↓ Giảm {:,.0f}₫</span>',
                -obj.price_change
            )
        elif obj.price_change > 0:
            return format_html(
                '<span style="color: red;">↑ Tăng {:,.0f}₫</span>',
                obj.price_change
            )
        return 'Không đổi'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin for carts."""
    
    list_display = [
        'cart_owner', 'cart_type', 'items_count',
        'subtotal_display', 'coupon_info',
        'last_activity', 'created_at'
    ]
    list_filter = [
        'abandonment_email_sent',
        ('user', admin.EmptyFieldListFilter),
        'created_at', 'last_activity_at'
    ]
    search_fields = ['user__email', 'session_key', 'coupon_code']
    raw_id_fields = ['user']
    readonly_fields = [
        'session_key', 'created_at', 'updated_at', 'last_activity_at',
        'cart_summary'
    ]
    inlines = [CartItemInline, SavedForLaterInline]
    
    fieldsets = (
        ('Thông tin', {
            'fields': ('user', 'session_key', 'expires_at', 'cart_summary')
        }),
        ('Coupon', {
            'fields': ('coupon_code', 'coupon_discount')
        }),
        ('Analytics', {
            'fields': (
                'last_activity_at', 'abandonment_email_sent',
                'utm_source', 'utm_medium', 'utm_campaign'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['cleanup_expired', 'send_abandonment_email', 'clear_carts']
    
    # Custom displays
    
    @admin.display(description='Chủ sở hữu')
    def cart_owner(self, obj):
        if obj.user:
            return obj.user.email
        return f"Guest: {obj.session_key[:15]}..."
    
    @admin.display(description='Loại')
    def cart_type(self, obj):
        if obj.user:
            return format_html(
                '<span style="color: green;">👤 User</span>'
            )
        return format_html(
            '<span style="color: gray;">👻 Guest</span>'
        )
    
    @admin.display(description='Items')
    def items_count(self, obj):
        count = obj.items.count()
        total_qty = obj.total_items
        return f"{count} ({total_qty})"
    
    @admin.display(description='Giá trị')
    def subtotal_display(self, obj):
        return f"{obj.subtotal:,.0f}₫"
    
    @admin.display(description='Coupon')
    def coupon_info(self, obj):
        if obj.coupon_code:
            return format_html(
                '<span style="color: green;">{} (-{:,.0f}₫)</span>',
                obj.coupon_code, obj.coupon_discount
            )
        return '-'
    
    @admin.display(description='Hoạt động cuối')
    def last_activity(self, obj):
        delta = timezone.now() - obj.last_activity_at
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    
    @admin.display(description='Tổng quan')
    def cart_summary(self, obj):
        return format_html(
            '<strong>Items:</strong> {} sản phẩm ({} qty)<br>'
            '<strong>Tạm tính:</strong> {:,.0f}₫<br>'
            '<strong>Giảm giá:</strong> {:,.0f}₫<br>'
            '<strong>Tiết kiệm:</strong> {:,.0f}₫<br>'
            '<strong>Tổng:</strong> {:,.0f}₫<br>'
            '<strong>Saved:</strong> {} items',
            obj.unique_items, obj.total_items,
            obj.subtotal,
            obj.coupon_discount,
            obj.total_savings,
            obj.total,
            obj.saved_items_count
        )
    
    # Actions
    
    @admin.action(description='Xóa giỏ hàng hết hạn')
    def cleanup_expired(self, request, queryset):
        from .services import CartService
        count = CartService.cleanup_expired_carts()
        self.message_user(request, f'Đã xóa {count} giỏ hàng hết hạn.')
    
    @admin.action(description='Đánh dấu đã gửi email nhắc')
    def send_abandonment_email(self, request, queryset):
        count = queryset.filter(user__isnull=False).update(abandonment_email_sent=True)
        self.message_user(request, f'Đã đánh dấu {count} giỏ hàng.')
    
    @admin.action(description='Xóa tất cả items trong giỏ')
    def clear_carts(self, request, queryset):
        count = 0
        for cart in queryset:
            count += cart.clear()
        self.message_user(request, f'Đã xóa {count} items.')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """Admin for cart items."""
    list_display = ['cart', 'product', 'quantity', 'unit_price', 'subtotal_display', 'stock_status']
    list_filter = ['created_at']
    search_fields = ['cart__user__email', 'product__name']
    raw_id_fields = ['cart', 'product']
    
    @admin.display(description='Thành tiền')
    def subtotal_display(self, obj):
        if obj.unit_price is None:
            return '-'
        return f"{obj.subtotal:,.0f}₫"
    
    @admin.display(description='Tồn kho')
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return 'Hết hàng'
        elif obj.exceeds_stock:
            return f'Vượt quá ({obj.available_quantity})'
        return 'OK'


@admin.register(SavedForLater)
class SavedForLaterAdmin(admin.ModelAdmin):
    """Admin for saved items."""
    list_display = ['cart', 'product', 'price_when_saved', 'current_price', 'price_status', 'created_at']
    list_filter = ['created_at']
    search_fields = ['cart__user__email', 'product__name']
    raw_id_fields = ['cart', 'product']
    
    @admin.display(description='Trạng thái')
    def price_status(self, obj):
        if obj.price_dropped:
            return f'↓ -{abs(obj.price_change):,.0f}₫'
        elif obj.price_change > 0:
            return f'↑ +{obj.price_change:,.0f}₫'
        return 'Không đổi'


@admin.register(CartEvent)
class CartEventAdmin(admin.ModelAdmin):
    """Admin for cart events."""
    list_display = ['cart', 'event_type', 'product', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['cart__user__email', 'product__name']
    raw_id_fields = ['cart', 'product']
    date_hierarchy = 'created_at'
    readonly_fields = ['cart', 'event_type', 'product', 'data', 'created_at']
