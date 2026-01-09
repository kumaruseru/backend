"""Commerce Shipping - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Shipment, ShipmentEvent, DeliveryAttempt, CODReconciliation


class ShipmentEventInline(TabularInline):
    model = ShipmentEvent
    extra = 0
    readonly_fields = ['status', 'description', 'location', 'occurred_at']
    ordering = ['-occurred_at']


class DeliveryAttemptInline(TabularInline):
    model = DeliveryAttempt
    extra = 0
    readonly_fields = ['attempt_number', 'attempted_at', 'fail_reason', 'notes']


@admin.register(Shipment)
class ShipmentAdmin(ModelAdmin):
    list_display = ['tracking_code', 'order_number', 'provider_badge', 'status_badge', 'cod_display', 'delivery_attempts', 'created_at']
    list_filter = ['status', 'provider', 'cod_collected', 'cod_transferred', 'created_at']
    search_fields = ['tracking_code', 'order__order_number', 'provider_order_id']
    raw_id_fields = ['order']
    readonly_fields = ['tracking_code', 'provider_order_id', 'provider_status', 'delivery_attempts', 'picked_up_at', 'delivered_at', 'returned_at', 'cancelled_at', 'last_location', 'last_status_update', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [ShipmentEventInline, DeliveryAttemptInline]

    fieldsets = (
        ('Order', {'fields': ('order', 'tracking_code', 'provider', 'provider_order_id')}),
        ('Status', {'fields': ('status', 'provider_status', 'last_location', 'last_status_update')}),
        ('Shipping', {'fields': ('weight', 'dimensions', 'service_type', 'expected_delivery')}),
        ('Fees', {'fields': ('shipping_fee', 'insurance_fee', 'cod_fee', 'total_fee')}),
        ('COD', {'fields': ('cod_amount', 'cod_collected', 'cod_transferred', 'cod_transfer_date')}),
        ('Delivery', {'fields': ('delivery_attempts', 'max_delivery_attempts', 'required_note', 'note')}),
        ('Timestamps', {'fields': ('picked_up_at', 'delivered_at', 'returned_at', 'cancelled_at'), 'classes': ('collapse',)}),
        ('Issues', {'fields': ('fail_reason', 'cancel_reason'), 'classes': ('collapse',)}),
    )

    actions = ['mark_picked_up', 'mark_in_transit', 'mark_delivered']

    @admin.display(description='Order')
    def order_number(self, obj):
        return obj.order.order_number

    @admin.display(description='Provider')
    def provider_badge(self, obj):
        colors = {'ghn': '#f97316', 'ghtk': '#22c55e', 'vtp': '#ef4444', 'manual': '#6b7280'}
        color = colors.get(obj.provider, '#6b7280')
        return format_html('<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, obj.get_provider_display())

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'picking': '#17a2b8', 'picked_up': '#6f42c1', 'in_transit': '#17a2b8', 'sorting': '#6c757d', 'out_for_delivery': '#fd7e14', 'delivered': '#28a745', 'failed': '#dc3545', 'waiting_return': '#ffc107', 'returning': '#fd7e14', 'returned': '#6c757d', 'cancelled': '#dc3545', 'exception': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        text_color = 'black' if obj.status in ['pending', 'waiting_return'] else 'white'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', color, text_color, obj.get_status_display())

    @admin.display(description='COD')
    def cod_display(self, obj):
        if obj.cod_amount > 0:
            icon = '✅' if obj.cod_collected else '⏳'
            return f"{icon} {obj.cod_amount:,.0f}₫"
        return '-'

    @admin.action(description='Mark as Picked Up')
    def mark_picked_up(self, request, queryset):
        for shipment in queryset.filter(status='pending'):
            shipment.update_status('picked_up', description='Picked up by admin')
        self.message_user(request, 'Shipments marked as picked up.')

    @admin.action(description='Mark as In Transit')
    def mark_in_transit(self, request, queryset):
        for shipment in queryset.filter(status='picked_up'):
            shipment.update_status('in_transit', description='In transit by admin')
        self.message_user(request, 'Shipments marked as in transit.')

    @admin.action(description='Mark as Delivered')
    def mark_delivered(self, request, queryset):
        for shipment in queryset.filter(status__in=['in_transit', 'out_for_delivery']):
            shipment.mark_delivered()
        self.message_user(request, 'Shipments marked as delivered.')


@admin.register(CODReconciliation)
class CODReconciliationAdmin(ModelAdmin):
    list_display = ['provider_display', 'reconciliation_date', 'status_badge', 'total_orders', 'amount_display', 'transferred_at']
    list_filter = ['provider', 'status', 'reconciliation_date']
    search_fields = ['transfer_reference']
    readonly_fields = ['total_orders', 'total_cod', 'total_shipping_fee', 'net_amount', 'created_at', 'updated_at']
    filter_horizontal = ['shipments']

    fieldsets = (
        ('Info', {'fields': ('provider', 'reconciliation_date', 'status')}),
        ('Amounts', {'fields': ('total_orders', 'total_cod', 'total_shipping_fee', 'net_amount')}),
        ('Transfer', {'fields': ('transferred_at', 'transfer_reference', 'notes')}),
        ('Shipments', {'fields': ('shipments',), 'classes': ('collapse',)}),
    )

    @admin.display(description='Provider')
    def provider_display(self, obj):
        return obj.get_provider_display()

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'confirmed': '#17a2b8', 'transferred': '#28a745', 'disputed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        text_color = 'black' if obj.status == 'pending' else 'white'
        return format_html('<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 3px;">{}</span>', color, text_color, obj.get_status_display())

    @admin.display(description='Amount')
    def amount_display(self, obj):
        return f"{obj.net_amount:,.0f}₫"
