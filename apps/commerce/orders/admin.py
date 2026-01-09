"""Commerce Orders - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Order, OrderItem, OrderStatusHistory, OrderNote


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_id', 'product_name', 'product_sku', 'quantity', 'unit_price', 'subtotal']
    fields = ['product_name', 'product_sku', 'quantity', 'unit_price', 'subtotal']

    @admin.display(description='Subtotal')
    def subtotal(self, obj):
        return f"{obj.subtotal:,.0f}"


class OrderStatusHistoryInline(TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'notes', 'created_at']
    ordering = ['-created_at']


class OrderNoteInline(TabularInline):
    model = OrderNote
    extra = 0
    fields = ['note_type', 'content', 'created_by', 'is_private', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ['order_number', 'recipient_name', 'phone', 'total_display', 'status_badge', 'payment_badge', 'source', 'created_at']
    list_filter = ['status', 'payment_status', 'payment_method', 'source', 'is_priority', 'created_at']
    search_fields = ['order_number', 'phone', 'recipient_name', 'user__email']
    raw_id_fields = ['user', 'cancelled_by']
    readonly_fields = ['order_number', 'created_at', 'updated_at', 'confirmed_at', 'paid_at', 'shipped_at', 'delivered_at', 'completed_at', 'cancelled_at']
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline, OrderStatusHistoryInline, OrderNoteInline]

    fieldsets = (
        ('Order Info', {'fields': ('order_number', 'user', 'source', 'status', 'is_priority')}),
        ('Shipping', {'fields': ('recipient_name', 'phone', 'email', 'address', 'ward', 'district', 'city')}),
        ('Payment', {'fields': ('payment_method', 'payment_status', 'subtotal', 'shipping_fee', 'discount', 'coupon_discount', 'total')}),
        ('Tracking', {'fields': ('tracking_code', 'shipping_provider')}),
        ('Notes', {'fields': ('customer_note', 'admin_note', 'is_gift', 'gift_message'), 'classes': ('collapse',)}),
        ('Cancellation', {'fields': ('cancel_reason', 'cancelled_by', 'cancelled_at'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('confirmed_at', 'paid_at', 'shipped_at', 'delivered_at', 'completed_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    actions = ['confirm_orders', 'mark_processing', 'mark_shipped', 'mark_delivered']

    @admin.display(description='Total')
    def total_display(self, obj):
        return f"{obj.total:,.0f}₫"

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107', 'confirmed': '#17a2b8', 'processing': '#6f42c1',
            'ready_to_ship': '#fd7e14', 'shipping': '#20c997', 'delivered': '#28a745',
            'completed': '#28a745', 'cancelled': '#dc3545', 'refunded': '#6c757d', 'failed': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        text_color = 'white' if obj.status not in ['pending'] else 'black'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, text_color, obj.get_status_display())

    @admin.display(description='Payment')
    def payment_badge(self, obj):
        colors = {'unpaid': '#dc3545', 'pending': '#ffc107', 'paid': '#28a745', 'failed': '#dc3545', 'refunded': '#6c757d'}
        color = colors.get(obj.payment_status, '#6c757d')
        return format_html('<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, obj.get_payment_status_display())

    @admin.action(description='Confirm selected orders')
    def confirm_orders(self, request, queryset):
        count = 0
        for order in queryset.filter(status='pending'):
            order.confirm(request.user)
            count += 1
        self.message_user(request, f'Confirmed {count} orders.')

    @admin.action(description='Mark as processing')
    def mark_processing(self, request, queryset):
        count = 0
        for order in queryset.filter(status__in=['pending', 'confirmed']):
            order.mark_processing(request.user)
            count += 1
        self.message_user(request, f'Marked {count} orders as processing.')

    @admin.action(description='Mark as shipped')
    def mark_shipped(self, request, queryset):
        count = 0
        for order in queryset.filter(status__in=['confirmed', 'processing', 'ready_to_ship']):
            order.ship('MANUAL', 'manual', request.user)
            count += 1
        self.message_user(request, f'Marked {count} orders as shipped.')

    @admin.action(description='Mark as delivered')
    def mark_delivered(self, request, queryset):
        count = 0
        for order in queryset.filter(status='shipping'):
            order.deliver(request.user)
            count += 1
        self.message_user(request, f'Marked {count} orders as delivered.')


@admin.register(OrderNote)
class OrderNoteAdmin(ModelAdmin):
    list_display = ['order', 'note_type', 'content_preview', 'created_by', 'is_private', 'created_at']
    list_filter = ['note_type', 'is_private', 'created_at']
    search_fields = ['order__order_number', 'content']
    raw_id_fields = ['order', 'created_by']

    @admin.display(description='Content')
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
