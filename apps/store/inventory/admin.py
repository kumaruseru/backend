"""Store Inventory - Admin Configuration."""
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import Warehouse, StockItem, StockMovement, StockAlert, InventoryCount, InventoryCountItem


class InventoryCountItemInline(TabularInline):
    model = InventoryCountItem
    extra = 0
    readonly_fields = ['stock', 'system_quantity', 'variance']
    fields = ['stock', 'system_quantity', 'counted_quantity', 'variance', 'notes']


@admin.register(Warehouse)
class WarehouseAdmin(ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'is_default', 'stock_count', 'created_at']
    list_filter = ['is_active', 'is_default']
    search_fields = ['name', 'code', 'address']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {'fields': ('name', 'code', 'address')}),
        ('Contact', {'fields': ('contact_name', 'contact_phone', 'contact_email')}),
        ('Settings', {'fields': ('is_active', 'is_default', 'allow_negative_stock')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Stock Items')
    def stock_count(self, obj):
        return obj.stock_items.count()


@admin.register(StockItem)
class StockItemAdmin(ModelAdmin):
    list_display = ['product_display', 'warehouse', 'quantity', 'reserved_quantity', 'available_display', 'stock_status_badge', 'last_restocked_at']
    list_filter = ['warehouse', 'updated_at']
    search_fields = ['product__name', 'product__sku']
    raw_id_fields = ['product', 'warehouse']
    readonly_fields = ['created_at', 'updated_at', 'last_sold_at', 'last_restocked_at']

    fieldsets = (
        ('Product', {'fields': ('product', 'warehouse')}),
        ('Stock Levels', {'fields': ('quantity', 'reserved_quantity', 'unit_cost')}),
        ('Thresholds', {'fields': ('low_stock_threshold', 'reorder_point', 'reorder_quantity')}),
        ('Timestamps', {'fields': ('last_restocked_at', 'last_sold_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Product')
    def product_display(self, obj):
        return f"{obj.product.name} ({obj.product.sku or '-'})"

    @admin.display(description='Available')
    def available_display(self, obj):
        return obj.available_quantity

    @admin.display(description='Status')
    def stock_status_badge(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Out</span>')
        elif obj.is_low_stock:
            return format_html('<span style="background: #ffc107; color: black; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Low</span>')
        return format_html('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">OK</span>')


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ['product_display', 'movement_type', 'quantity_change_display', 'reason', 'reference', 'created_by', 'created_at']
    list_filter = ['movement_type', 'reason', 'created_at']
    search_fields = ['stock__product__name', 'reference', 'notes']
    raw_id_fields = ['stock', 'created_by']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    @admin.display(description='Product')
    def product_display(self, obj):
        return obj.stock.product.name

    @admin.display(description='Change')
    def quantity_change_display(self, obj):
        if obj.quantity_change > 0:
            return format_html('<span style="color: green;">+{}</span>', obj.quantity_change)
        return format_html('<span style="color: red;">{}</span>', obj.quantity_change)


@admin.register(StockAlert)
class StockAlertAdmin(ModelAdmin):
    list_display = ['product_display', 'alert_type', 'current_quantity', 'threshold', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'is_resolved', 'created_at']
    search_fields = ['stock__product__name']
    raw_id_fields = ['stock', 'resolved_by']
    readonly_fields = ['created_at', 'resolved_at']

    actions = ['resolve_alerts']

    @admin.display(description='Product')
    def product_display(self, obj):
        return obj.stock.product.name

    @admin.action(description='Resolve selected alerts')
    def resolve_alerts(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(is_resolved=True, resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'Resolved {count} alerts.')


@admin.register(InventoryCount)
class InventoryCountAdmin(ModelAdmin):
    list_display = ['name', 'warehouse', 'status', 'items_count', 'started_at', 'completed_at']
    list_filter = ['status', 'warehouse', 'created_at']
    search_fields = ['name']
    raw_id_fields = ['warehouse', 'created_by']
    readonly_fields = ['started_at', 'completed_at', 'created_at', 'updated_at']
    inlines = [InventoryCountItemInline]

    fieldsets = (
        ('Basic Info', {'fields': ('name', 'warehouse', 'status', 'notes')}),
        ('Audit', {'fields': ('created_by', 'started_at', 'completed_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    actions = ['start_counts', 'complete_counts']

    @admin.display(description='Items')
    def items_count(self, obj):
        return obj.items.count()

    @admin.action(description='Start selected counts')
    def start_counts(self, request, queryset):
        for count in queryset.filter(status='draft'):
            count.start()
        self.message_user(request, f'Started inventory counts.')

    @admin.action(description='Complete selected counts')
    def complete_counts(self, request, queryset):
        for count in queryset.filter(status='in_progress'):
            count.complete()
        self.message_user(request, f'Completed inventory counts.')
