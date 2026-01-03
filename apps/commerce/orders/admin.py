"""
Commerce Orders - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Status badges
- Inline items and history
- Bulk actions
- Advanced filtering
- Export capability
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Order, OrderItem, OrderStatusHistory, OrderNote


class OrderItemInline(admin.TabularInline):
    """Inline for order items."""
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'product_sku', 'unit_price', 'subtotal_display']
    fields = [
        'product', 'product_name', 'product_sku', 'product_image',
        'quantity', 'unit_price', 'subtotal_display', 'returned_quantity'
    ]
    
    @admin.display(description='Thành tiền')
    def subtotal_display(self, obj):
        if obj.unit_price is None or obj.quantity is None:
            return '-'
        return f"{obj.subtotal:,.0f}₫"


class OrderStatusHistoryInline(admin.TabularInline):
    """Inline for status history."""
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'notes', 'created_at']
    can_delete = False
    max_num = 0
    
    def has_add_permission(self, request, obj=None):
        return False


class OrderNoteInline(admin.TabularInline):
    """Inline for order notes."""
    model = OrderNote
    extra = 0
    readonly_fields = ['created_by', 'created_at']
    fields = ['note_type', 'content', 'is_private', 'created_by', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin for orders."""
    
    list_display = [
        'order_number', 'customer_info', 'status_badge',
        'payment_badge', 'total_display', 'item_count',
        'days_old', 'created_at'
    ]
    list_filter = [
        'status', 'payment_status', 'payment_method',
        'source', 'is_priority', 'is_gift',
        'created_at', 'delivered_at'
    ]
    search_fields = [
        'order_number', 'phone', 'email',
        'recipient_name', 'user__email',
        'tracking_code'
    ]
    raw_id_fields = ['user', 'coupon', 'cancelled_by']
    readonly_fields = [
        'order_number', 'created_at', 'updated_at',
        'confirmed_at', 'paid_at', 'shipped_at', 'delivered_at',
        'completed_at', 'cancelled_at',
        'customer_summary', 'shipping_summary', 'payment_summary', 'timeline'
    ]
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline, OrderStatusHistoryInline, OrderNoteInline]
    
    fieldsets = (
        ('Thông tin đơn hàng', {
            'fields': (
                'order_number', 'user', 'status', 'source',
                'is_priority', 'customer_summary'
            )
        }),
        ('Giao hàng', {
            'fields': (
                'shipping_summary',
                'recipient_name', 'phone', 'email',
                'address', 'ward', 'district', 'city',
                'district_id', 'ward_code'
            )
        }),
        ('Thanh toán', {
            'fields': (
                'payment_summary',
                'payment_method', 'payment_status'
            )
        }),
        ('Số tiền', {
            'fields': (
                'subtotal', 'shipping_fee', 'insurance_fee',
                'discount', 'coupon', 'coupon_code', 'coupon_discount',
                'tax', 'total', 'currency'
            )
        }),
        ('Vận chuyển', {
            'fields': ('tracking_code', 'shipping_provider'),
            'classes': ('collapse',)
        }),
        ('Ghi chú', {
            'fields': (
                'customer_note', 'admin_note',
                'is_gift', 'gift_message'
            ),
            'classes': ('collapse',)
        }),
        ('Hủy đơn', {
            'fields': ('cancel_reason', 'cancelled_by', 'cancelled_at'),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': (
                'timeline',
                'created_at', 'confirmed_at', 'paid_at',
                'shipped_at', 'delivered_at', 'completed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('ip_address', 'utm_source', 'utm_medium', 'utm_campaign'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'confirm_orders', 'mark_processing',
        'mark_shipped', 'mark_delivered',
        'export_csv'
    ]
    
    # Custom displays
    
    @admin.display(description='Khách hàng')
    def customer_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.recipient_name, obj.phone
        )
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'confirmed': '#1E90FF',
            'processing': '#9370DB',
            'ready_to_ship': '#20B2AA',
            'shipping': '#32CD32',
            'delivered': '#228B22',
            'completed': '#006400',
            'cancelled': '#DC143C',
            'refunded': '#808080',
            'failed': '#8B0000'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Thanh toán')
    def payment_badge(self, obj):
        colors = {
            'unpaid': '#FFA500',
            'pending': '#1E90FF',
            'paid': '#228B22',
            'failed': '#DC143C',
            'partial_refund': '#FF8C00',
            'refunded': '#808080'
        }
        color = colors.get(obj.payment_status, '#000')
        method = obj.get_payment_method_display()
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">{}</span><br>'
            '<small>{}</small>',
            color, obj.get_payment_status_display(), method
        )
    
    @admin.display(description='Tổng')
    def total_display(self, obj):
        return f"{obj.total:,.0f}₫"
    
    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.item_count
    
    @admin.display(description='Ngày')
    def days_old(self, obj):
        delta = timezone.now() - obj.created_at
        return f"{delta.days}d"
    
    @admin.display(description='Khách hàng')
    def customer_summary(self, obj):
        return format_html(
            '<strong>Email:</strong> {}<br>'
            '<strong>SĐT:</strong> {}<br>'
            '<strong>Số đơn:</strong> {}',
            obj.user.email,
            obj.phone,
            obj.user.orders.count()
        )
    
    @admin.display(description='Địa chỉ giao hàng')
    def shipping_summary(self, obj):
        return format_html(
            '<strong>{}</strong><br>'
            '📞 {}<br>'
            '📍 {}',
            obj.recipient_name,
            obj.phone,
            obj.full_address
        )
    
    @admin.display(description='Tổng kết thanh toán')
    def payment_summary(self, obj):
        return format_html(
            '<strong>Phương thức:</strong> {}<br>'
            '<strong>Trạng thái:</strong> {}<br>'
            '<strong>Tổng:</strong> {:,.0f}₫',
            obj.get_payment_method_display(),
            obj.get_payment_status_display(),
            obj.total
        )
    
    @admin.display(description='Timeline')
    def timeline(self, obj):
        events = []
        if obj.created_at:
            events.append(f"🛒 Tạo đơn: {obj.created_at.strftime('%d/%m %H:%M')}")
        if obj.confirmed_at:
            events.append(f"✓ Xác nhận: {obj.confirmed_at.strftime('%d/%m %H:%M')}")
        if obj.paid_at:
            events.append(f"💰 Thanh toán: {obj.paid_at.strftime('%d/%m %H:%M')}")
        if obj.shipped_at:
            events.append(f"🚚 Giao hàng: {obj.shipped_at.strftime('%d/%m %H:%M')}")
        if obj.delivered_at:
            events.append(f"📦 Đã giao: {obj.delivered_at.strftime('%d/%m %H:%M')}")
        if obj.completed_at:
            events.append(f"✅ Hoàn thành: {obj.completed_at.strftime('%d/%m %H:%M')}")
        if obj.cancelled_at:
            events.append(f"❌ Hủy: {obj.cancelled_at.strftime('%d/%m %H:%M')}")
        
        return format_html('<br>'.join(events))
    
    # Actions
    
    @admin.action(description='Xác nhận đơn hàng')
    def confirm_orders(self, request, queryset):
        count = 0
        for order in queryset.filter(status='pending'):
            order.confirm(request.user)
            count += 1
        self.message_user(request, f'Đã xác nhận {count} đơn hàng.')
    
    @admin.action(description='Đánh dấu đang xử lý')
    def mark_processing(self, request, queryset):
        count = 0
        for order in queryset.filter(status__in=['pending', 'confirmed']):
            order.mark_processing(request.user)
            count += 1
        self.message_user(request, f'Đã cập nhật {count} đơn hàng.')
    
    @admin.action(description='Đánh dấu đã giao cho vận chuyển')
    def mark_shipped(self, request, queryset):
        count = 0
        for order in queryset.filter(status__in=['confirmed', 'processing', 'ready_to_ship']):
            if order.tracking_code:
                order.ship(order.tracking_code, order.shipping_provider or 'ghn', request.user)
                count += 1
        self.message_user(request, f'Đã cập nhật {count} đơn hàng.')
    
    @admin.action(description='Đánh dấu đã giao hàng')
    def mark_delivered(self, request, queryset):
        count = 0
        for order in queryset.filter(status='shipping'):
            order.deliver(request.user)
            count += 1
        self.message_user(request, f'Đã cập nhật {count} đơn hàng.')
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'Mã đơn', 'Khách hàng', 'SĐT', 'Trạng thái',
            'Thanh toán', 'Phương thức', 'Tổng', 'Ngày tạo'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.order_number,
                obj.recipient_name,
                obj.phone,
                obj.get_status_display(),
                obj.get_payment_status_display(),
                obj.get_payment_method_display(),
                obj.total,
                obj.created_at.strftime('%d/%m/%Y %H:%M')
            ])
        
        return response


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin for order items."""
    list_display = ['order', 'product_name', 'quantity', 'unit_price', 'subtotal_display']
    list_filter = ['created_at']
    search_fields = ['order__order_number', 'product_name', 'product_sku']
    raw_id_fields = ['order', 'product']
    
    @admin.display(description='Thành tiền')
    def subtotal_display(self, obj):
        if obj.unit_price is None or obj.quantity is None:
            return '-'
        return f"{obj.subtotal:,.0f}₫"


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """Admin for status history."""
    list_display = ['order', 'old_status', 'new_status', 'changed_by', 'created_at']
    list_filter = ['new_status', 'created_at']
    search_fields = ['order__order_number']
    raw_id_fields = ['order', 'changed_by']
    readonly_fields = ['created_at']


@admin.register(OrderNote)
class OrderNoteAdmin(admin.ModelAdmin):
    """Admin for order notes."""
    list_display = ['order', 'note_type', 'short_content', 'created_by', 'is_private', 'created_at']
    list_filter = ['note_type', 'is_private', 'created_at']
    search_fields = ['order__order_number', 'content']
    raw_id_fields = ['order', 'created_by']
    
    @admin.display(description='Nội dung')
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
