"""Store Inventory - Serializers."""
from rest_framework import serializers
from .models import Warehouse, StockItem, StockMovement, StockAlert, InventoryCount, InventoryCountItem


class WarehouseSerializer(serializers.ModelSerializer):
    total_stock_value = serializers.ReadOnlyField()
    stock_count = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'code', 'address', 'contact_name', 'contact_phone', 'contact_email', 'is_active', 'is_default', 'allow_negative_stock', 'total_stock_value', 'stock_count', 'created_at']

    def get_stock_count(self, obj) -> int:
        return obj.stock_items.count()


class WarehouseSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'code']


class StockItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id')
    product_name = serializers.CharField(source='product.name')
    product_sku = serializers.CharField(source='product.sku')
    product_image = serializers.SerializerMethodField()
    warehouse = WarehouseSimpleSerializer(read_only=True)
    available_quantity = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    needs_reorder = serializers.ReadOnlyField()
    stock_status = serializers.ReadOnlyField()
    stock_value = serializers.ReadOnlyField()

    class Meta:
        model = StockItem
        fields = ['id', 'product_id', 'product_name', 'product_sku', 'product_image', 'warehouse', 'quantity', 'reserved_quantity', 'available_quantity', 'low_stock_threshold', 'reorder_point', 'reorder_quantity', 'is_in_stock', 'is_low_stock', 'is_out_of_stock', 'needs_reorder', 'stock_status', 'stock_value', 'unit_cost', 'last_restocked_at', 'last_sold_at', 'created_at', 'updated_at']

    def get_product_image(self, obj) -> str:
        return obj.product.primary_image_url if obj.product else ''


class StockItemListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name')
    product_sku = serializers.CharField(source='product.sku')
    available_quantity = serializers.ReadOnlyField()
    stock_status = serializers.ReadOnlyField()

    class Meta:
        model = StockItem
        fields = ['id', 'product_name', 'product_sku', 'quantity', 'reserved_quantity', 'available_quantity', 'stock_status']


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='stock.product.name')
    movement_type_display = serializers.CharField(source='get_movement_type_display')
    reason_display = serializers.CharField(source='get_reason_display')
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = ['id', 'product_name', 'movement_type', 'movement_type_display', 'quantity_change', 'quantity_before', 'quantity_after', 'reason', 'reason_display', 'reference', 'notes', 'unit_cost', 'created_by_name', 'created_at']

    def get_created_by_name(self, obj) -> str:
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='stock.product.name')
    product_sku = serializers.CharField(source='stock.product.sku')
    alert_type_display = serializers.CharField(source='get_alert_type_display')

    class Meta:
        model = StockAlert
        fields = ['id', 'product_name', 'product_sku', 'alert_type', 'alert_type_display', 'threshold', 'current_quantity', 'is_resolved', 'resolved_at', 'notes', 'created_at']


class InventoryCountItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='stock.product.name')
    product_sku = serializers.CharField(source='stock.product.sku')
    variance = serializers.ReadOnlyField()
    variance_value = serializers.ReadOnlyField()

    class Meta:
        model = InventoryCountItem
        fields = ['id', 'product_name', 'product_sku', 'system_quantity', 'counted_quantity', 'variance', 'variance_value', 'notes', 'counted_at']


class InventoryCountSerializer(serializers.ModelSerializer):
    warehouse = WarehouseSimpleSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display')
    items = InventoryCountItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_variance = serializers.SerializerMethodField()

    class Meta:
        model = InventoryCount
        fields = ['id', 'name', 'warehouse', 'status', 'status_display', 'started_at', 'completed_at', 'notes', 'items', 'total_items', 'total_variance', 'created_at']

    def get_total_items(self, obj) -> int:
        return obj.items.count()

    def get_total_variance(self, obj) -> int:
        return sum(item.variance for item in obj.items.all() if item.counted_quantity is not None)


class InventoryCountListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display')
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = InventoryCount
        fields = ['id', 'name', 'status', 'status_display', 'items_count', 'created_at']

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class StockAdjustSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=100, required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class StockAddSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=0, required=False)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class StockReserveSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(max_length=100, required=True)


class StockTransferSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    from_warehouse_id = serializers.IntegerField()
    to_warehouse_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BulkStockUpdateSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), min_length=1)


class InventoryCountCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    warehouse_id = serializers.IntegerField(required=False)
    product_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class InventoryCountItemUpdateSerializer(serializers.Serializer):
    counted_quantity = serializers.IntegerField(min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)


class InventoryStatisticsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    total_stock_value = serializers.DecimalField(max_digits=15, decimal_places=0)
    in_stock_count = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()
    pending_alerts = serializers.IntegerField()
    movements_today = serializers.IntegerField()
    items_sold_today = serializers.IntegerField()
    items_received_today = serializers.IntegerField()
