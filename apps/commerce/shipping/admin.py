"""
Commerce Shipping - Production-Ready Admin Configuration.

Comprehensive admin interface with:
- Status badges
- Inline events and delivery attempts
- Bulk actions
- Statistics dashboard
- Export capability
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation


class ShipmentEventInline(admin.TabularInline):
    """Inline for shipment events."""
    model = ShipmentEvent
    extra = 0
    readonly_fields = ['status', 'description', 'location', 'occurred_at', 'created_at']
    can_delete = False
    max_num = 0
    
    def has_add_permission(self, request, obj=None):
        return False


class DeliveryAttemptInline(admin.TabularInline):
    """Inline for delivery attempts."""
    model = DeliveryAttempt
    extra = 0
    readonly_fields = ['attempt_number', 'attempted_at', 'fail_reason', 'notes']
    fields = ['attempt_number', 'attempted_at', 'fail_reason', 'notes', 'rescheduled_to']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    """Admin for shipments."""
    
    list_display = [
        'tracking_code', 'order_link', 'provider_badge',
        'status_badge', 'cod_info', 'delivery_info',
        'days_display', 'created_at'
    ]
    list_filter = [
        'status', 'provider', 'cod_collected', 'cod_transferred',
        'created_at', 'delivered_at'
    ]
    search_fields = [
        'tracking_code', 'provider_order_id',
        'order__order_number', 'order__user__email',
        'order__recipient_name', 'order__phone'
    ]
    raw_id_fields = ['order']
    readonly_fields = [
        'tracking_code', 'provider_order_id', 'provider_data',
        'created_at', 'updated_at', 'picked_up_at', 'delivered_at',
        'returned_at', 'cancelled_at', 'last_status_update',
        'order_info', 'fee_summary', 'timeline'
    ]
    date_hierarchy = 'created_at'
    inlines = [ShipmentEventInline, DeliveryAttemptInline]
    
    fieldsets = (
        ('Thông tin vận đơn', {
            'fields': (
                'order', 'order_info',
                'tracking_code', 'provider_order_id',
                'provider', 'status', 'provider_status'
            )
        }),
        ('Chi tiết', {
            'fields': (
                'weight', 'dimensions', 'service_type', 'service_id',
                'note', 'required_note'
            )
        }),
        ('Phí vận chuyển', {
            'fields': ('fee_summary', 'shipping_fee', 'insurance_fee', 'cod_fee', 'total_fee')
        }),
        ('COD', {
            'fields': (
                'cod_amount', 'cod_collected', 'cod_transferred', 'cod_transfer_date'
            )
        }),
        ('Giao hàng', {
            'fields': (
                'expected_delivery', 'delivery_attempts', 'max_delivery_attempts',
                'last_location'
            )
        }),
        ('Vấn đề', {
            'fields': ('fail_reason', 'cancel_reason'),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': (
                'timeline', 'created_at', 'picked_up_at', 'delivered_at',
                'returned_at', 'cancelled_at', 'last_status_update'
            ),
            'classes': ('collapse',)
        }),
        ('Provider Data', {
            'fields': ('provider_data',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['sync_tracking', 'export_csv']
    
    # Custom displays
    
    @admin.display(description='Đơn hàng', ordering='order__order_number')
    def order_link(self, obj):
        return format_html(
            '<a href="/admin/orders/order/{}/change/">{}</a>',
            obj.order.id, obj.order.order_number
        )
    
    @admin.display(description='Provider')
    def provider_badge(self, obj):
        colors = {
            'ghn': '#EE4D2D',
            'ghtk': '#00B14F',
            'vtp': '#EF4123',
            'vnpost': '#E60012',
            'jnt': '#D71920',
            'manual': '#6B7280'
        }
        color = colors.get(obj.provider, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_provider_display()
        )
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'picking': '#FFD700',
            'picked_up': '#1E90FF',
            'in_transit': '#9370DB',
            'sorting': '#8A2BE2',
            'out_for_delivery': '#32CD32',
            'delivered': '#228B22',
            'failed': '#DC143C',
            'waiting_return': '#FF6347',
            'returning': '#FF8C00',
            'returned': '#A0522D',
            'cancelled': '#808080',
            'exception': '#8B0000'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='COD')
    def cod_info(self, obj):
        if obj.cod_amount == 0:
            return '-'
        
        status_icon = '✅' if obj.cod_collected else '⏳'
        transfer_icon = '💰' if obj.cod_transferred else ''
        
        return format_html(
            '{} {:,.0f}₫ {}',
            status_icon, obj.cod_amount, transfer_icon
        )
    
    @admin.display(description='Giao hàng')
    def delivery_info(self, obj):
        if obj.delivered_at:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                obj.delivered_at.strftime('%d/%m %H:%M')
            )
        elif obj.expected_delivery:
            return format_html(
                'Dự kiến: {}',
                obj.expected_delivery.strftime('%d/%m')
            )
        return '-'
    
    @admin.display(description='Ngày')
    def days_display(self, obj):
        if obj.is_final:
            return f"{obj.days_in_transit}d"
        delta = timezone.now() - obj.created_at
        return f"{delta.days}d"
    
    @admin.display(description='Thông tin đơn hàng')
    def order_info(self, obj):
        order = obj.order
        return format_html(
            '<strong>Mã đơn:</strong> {}<br>'
            '<strong>Người nhận:</strong> {}<br>'
            '<strong>SĐT:</strong> {}<br>'
            '<strong>Địa chỉ:</strong> {}',
            order.order_number,
            order.recipient_name,
            order.phone,
            order.full_address
        )
    
    @admin.display(description='Tổng phí')
    def fee_summary(self, obj):
        return format_html(
            '<strong>Ship:</strong> {:,.0f}₫<br>'
            '<strong>Bảo hiểm:</strong> {:,.0f}₫<br>'
            '<strong>COD:</strong> {:,.0f}₫<br>'
            '<strong>Tổng:</strong> {:,.0f}₫',
            obj.shipping_fee, obj.insurance_fee, obj.cod_fee, obj.total_fee
        )
    
    @admin.display(description='Timeline')
    def timeline(self, obj):
        events = []
        if obj.created_at:
            events.append(f"Tạo đơn: {obj.created_at.strftime('%d/%m %H:%M')}")
        if obj.picked_up_at:
            events.append(f"Lấy hàng: {obj.picked_up_at.strftime('%d/%m %H:%M')}")
        if obj.delivered_at:
            events.append(f"Giao hàng: {obj.delivered_at.strftime('%d/%m %H:%M')}")
        if obj.returned_at:
            events.append(f"Trả hàng: {obj.returned_at.strftime('%d/%m %H:%M')}")
        if obj.cancelled_at:
            events.append(f"Hủy: {obj.cancelled_at.strftime('%d/%m %H:%M')}")
        
        return format_html('<br>'.join(events))
    
    # Actions
    
    @admin.action(description='Đồng bộ tracking từ provider')
    def sync_tracking(self, request, queryset):
        from .services import ShippingService
        count = 0
        for shipment in queryset.filter(provider='ghn', status__in=[
            'pending', 'picking', 'picked_up', 'in_transit',
            'sorting', 'out_for_delivery'
        ]):
            try:
                ShippingService.sync_tracking(shipment)
                count += 1
            except Exception:
                pass
        self.message_user(request, f'Đã đồng bộ {count} vận đơn.')
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="shipments.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'Mã vận đơn', 'Mã đơn hàng', 'Provider', 'Trạng thái',
            'COD', 'Đã thu', 'Phí ship', 'Ngày tạo', 'Ngày giao'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.tracking_code,
                obj.order.order_number,
                obj.get_provider_display(),
                obj.get_status_display(),
                obj.cod_amount,
                'Có' if obj.cod_collected else 'Chưa',
                obj.shipping_fee,
                obj.created_at.strftime('%d/%m/%Y %H:%M'),
                obj.delivered_at.strftime('%d/%m/%Y %H:%M') if obj.delivered_at else ''
            ])
        
        return response


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    """Admin for shipment events."""
    list_display = ['shipment', 'status', 'description', 'location', 'occurred_at']
    list_filter = ['status', 'occurred_at']
    search_fields = ['shipment__tracking_code', 'description']
    raw_id_fields = ['shipment']
    date_hierarchy = 'occurred_at'


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    """Admin for delivery attempts."""
    list_display = ['shipment', 'attempt_number', 'fail_reason', 'attempted_at', 'rescheduled_to']
    list_filter = ['fail_reason', 'attempted_at']
    search_fields = ['shipment__tracking_code']
    raw_id_fields = ['shipment']


@admin.register(CODReconciliation)
class CODReconciliationAdmin(admin.ModelAdmin):
    """Admin for COD reconciliation."""
    list_display = [
        'reconciliation_date', 'provider', 'status',
        'total_orders', 'total_cod_display', 'net_amount_display',
        'transferred_at'
    ]
    list_filter = ['status', 'provider', 'reconciliation_date']
    search_fields = ['transfer_reference']
    date_hierarchy = 'reconciliation_date'
    filter_horizontal = ['shipments']
    
    @admin.display(description='Tổng COD')
    def total_cod_display(self, obj):
        return f"{obj.total_cod:,.0f}₫"
    
    @admin.display(description='Thực nhận')
    def net_amount_display(self, obj):
        return f"{obj.net_amount:,.0f}₫"
