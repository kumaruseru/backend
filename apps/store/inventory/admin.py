"""
Store Inventory - Production-Ready Admin Configuration.

Comprehensive admin with:
- Stock status badges
- Movement history inline
- Bulk operations
- Statistics dashboard
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from .models import Warehouse, StockItem, StockMovement, StockAlert, InventoryCount, InventoryCountItem


class StockMovementInline(admin.TabularInline):
    """Inline for stock movements."""
    model = StockMovement
    extra = 0
    readonly_fields = [
        'movement_type', 'quantity_change', 'quantity_before', 'quantity_after',
        'reason', 'reference', 'notes', 'created_by', 'created_at'
    ]
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class StockAlertInline(admin.TabularInline):
    """Inline for stock alerts."""
    model = StockAlert
    extra = 0
    fields = ['alert_type', 'threshold', 'current_quantity', 'is_resolved', 'created_at']
    readonly_fields = ['alert_type', 'threshold', 'current_quantity', 'created_at']
    can_delete = False


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    """Admin for warehouses."""
    
    list_display = ['name', 'code', 'is_active', 'is_default', 'stock_count', 'total_value']
    list_filter = ['is_active', 'is_default']
    search_fields = ['name', 'code', 'address']
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'code', 'address')
        }),
        ('Liên hệ', {
            'fields': ('contact_name', 'contact_phone', 'contact_email'),
            'classes': ('collapse',)
        }),
        ('Cài đặt', {
            'fields': ('is_active', 'is_default', 'allow_negative_stock')
        }),
    )
    
    @admin.display(description='Số SP')
    def stock_count(self, obj):
        return obj.stock_items.count()
    
    @admin.display(description='Tổng giá trị')
    def total_value(self, obj):
        return f"{obj.total_stock_value:,.0f}₫"


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    """Admin for stock items."""
    
    list_display = [
        'product_name', 'sku', 'warehouse',
        'quantity_display', 'reserved_display', 'available_display',
        'stock_status_badge', 'last_movement'
    ]
    list_filter = ['warehouse', 'last_restocked_at']
    search_fields = ['product__name', 'product__sku']
    raw_id_fields = ['product']
    readonly_fields = ['last_restocked_at', 'last_sold_at', 'created_at', 'updated_at']
    inlines = [StockMovementInline, StockAlertInline]
    
    fieldsets = (
        ('Sản phẩm', {
            'fields': ('product', 'warehouse')
        }),
        ('Số lượng', {
            'fields': ('quantity', 'reserved_quantity')
        }),
        ('Ngưỡng', {
            'fields': ('low_stock_threshold', 'reorder_point', 'reorder_quantity')
        }),
        ('Chi phí', {
            'fields': ('unit_cost',),
            'classes': ('collapse',)
        }),
        ('Thời gian', {
            'fields': ('last_restocked_at', 'last_sold_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_low_stock_check', 'export_csv']
    
    @admin.display(description='Sản phẩm')
    def product_name(self, obj):
        return obj.product.name
    
    @admin.display(description='SKU')
    def sku(self, obj):
        return obj.product.sku or '-'
    
    @admin.display(description='Tồn kho')
    def quantity_display(self, obj):
        if obj.quantity <= 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.quantity)
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', obj.quantity)
        return obj.quantity
    
    @admin.display(description='Đã đặt')
    def reserved_display(self, obj):
        if obj.reserved_quantity > 0:
            return format_html('<span style="color: blue;">{}</span>', obj.reserved_quantity)
        return 0
    
    @admin.display(description='Khả dụng')
    def available_display(self, obj):
        available = obj.available_quantity
        if available <= 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', available)
        return available
    
    @admin.display(description='Trạng thái')
    def stock_status_badge(self, obj):
        if obj.is_out_of_stock:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 2px 8px; '
                'border-radius: 3px; font-size: 11px;">Hết hàng</span>'
            )
        elif obj.is_low_stock:
            return format_html(
                '<span style="background: #ffc107; color: black; padding: 2px 8px; '
                'border-radius: 3px; font-size: 11px;">Sắp hết</span>'
            )
        return format_html(
            '<span style="background: #28a745; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">Còn hàng</span>'
        )
    
    @admin.display(description='Cập nhật')
    def last_movement(self, obj):
        movement = obj.movements.first()
        if movement:
            return format_html(
                '{}<br><small style="color: #666;">{}</small>',
                movement.get_reason_display(),
                movement.created_at.strftime('%d/%m %H:%M')
            )
        return '-'
    
    @admin.action(description='Export CSV')
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow(['SKU', 'Tên SP', 'Kho', 'Tồn kho', 'Đã đặt', 'Khả dụng', 'Trạng thái'])
        
        for obj in queryset.select_related('product', 'warehouse'):
            writer.writerow([
                obj.product.sku or '',
                obj.product.name,
                obj.warehouse.name if obj.warehouse else 'Mặc định',
                obj.quantity,
                obj.reserved_quantity,
                obj.available_quantity,
                obj.stock_status
            ])
        
        return response


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Admin for stock movements."""
    
    list_display = [
        'created_at', 'product_name', 'movement_badge',
        'quantity_change_display', 'quantity_before', 'quantity_after',
        'reason', 'reference', 'created_by'
    ]
    list_filter = ['movement_type', 'reason', 'created_at', 'stock__warehouse']
    search_fields = ['stock__product__name', 'stock__product__sku', 'reference']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'stock', 'movement_type', 'quantity_change', 'quantity_before', 'quantity_after',
        'reason', 'reference', 'unit_cost', 'notes', 'created_by', 'created_at'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    @admin.display(description='Sản phẩm')
    def product_name(self, obj):
        return obj.stock.product.name
    
    @admin.display(description='Loại')
    def movement_badge(self, obj):
        colors = {
            'in': '#28a745',
            'out': '#dc3545',
            'reserve': '#17a2b8',
            'release': '#6c757d',
            'adjustment': '#ffc107',
            'transfer': '#6f42c1',
        }
        color = colors.get(obj.movement_type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_movement_type_display()
        )
    
    @admin.display(description='Thay đổi')
    def quantity_change_display(self, obj):
        if obj.quantity_change > 0:
            return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.quantity_change)
        return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.quantity_change)


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    """Admin for stock alerts."""
    
    list_display = ['created_at', 'product_name', 'alert_type_badge', 'current_quantity', 'is_resolved_badge']
    list_filter = ['alert_type', 'is_resolved', 'created_at']
    search_fields = ['stock__product__name']
    readonly_fields = ['stock', 'alert_type', 'threshold', 'current_quantity', 'created_at']
    
    actions = ['resolve_alerts']
    
    @admin.display(description='Sản phẩm')
    def product_name(self, obj):
        return obj.stock.product.name
    
    @admin.display(description='Loại')
    def alert_type_badge(self, obj):
        colors = {
            'low_stock': '#ffc107',
            'out_of_stock': '#dc3545',
            'reorder': '#17a2b8',
            'expiring': '#6f42c1',
        }
        color = colors.get(obj.alert_type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_alert_type_display()
        )
    
    @admin.display(description='Đã xử lý')
    def is_resolved_badge(self, obj):
        if obj.is_resolved:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    
    @admin.action(description='Đánh dấu đã xử lý')
    def resolve_alerts(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_resolved=False).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        self.message_user(request, f'Đã xử lý {count} cảnh báo.')


class InventoryCountItemInline(admin.TabularInline):
    """Inline for inventory count items."""
    model = InventoryCountItem
    extra = 0
    fields = ['stock', 'system_quantity', 'counted_quantity', 'variance', 'notes']
    readonly_fields = ['stock', 'system_quantity', 'variance']
    
    @admin.display(description='Chênh lệch')
    def variance(self, obj):
        v = obj.variance
        if v > 0:
            return format_html('<span style="color: green;">+{}</span>', v)
        elif v < 0:
            return format_html('<span style="color: red;">{}</span>', v)
        return 0


@admin.register(InventoryCount)
class InventoryCountAdmin(admin.ModelAdmin):
    """Admin for inventory counts."""
    
    list_display = ['name', 'warehouse', 'status_badge', 'items_count', 'total_variance', 'created_at']
    list_filter = ['status', 'warehouse', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_by', 'started_at', 'completed_at', 'created_at']
    inlines = [InventoryCountItemInline]
    
    @admin.display(description='Trạng thái')
    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'in_progress': '#ffc107',
            'completed': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    @admin.display(description='Số items')
    def items_count(self, obj):
        return obj.items.count()
    
    @admin.display(description='Chênh lệch')
    def total_variance(self, obj):
        total = sum(item.variance for item in obj.items.all() if item.counted_quantity is not None)
        if total > 0:
            return format_html('<span style="color: green;">+{}</span>', total)
        elif total < 0:
            return format_html('<span style="color: red;">{}</span>', total)
        return 0
