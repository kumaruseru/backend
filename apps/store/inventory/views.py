"""Store Inventory - API Views."""
from django.db import models
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.core.exceptions import DomainException
from .models import Warehouse, StockItem, StockMovement, StockAlert, InventoryCount
from .serializers import (
    WarehouseSerializer,
    StockItemSerializer, StockItemListSerializer, StockMovementSerializer,
    StockAlertSerializer,
    InventoryCountSerializer, InventoryCountListSerializer, InventoryCountItemSerializer,
    StockAdjustSerializer, StockAddSerializer, StockReserveSerializer, StockTransferSerializer,
    InventoryCountCreateSerializer, InventoryCountItemUpdateSerializer,
    InventoryStatisticsSerializer
)
from .services import InventoryService


class WarehouseListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = WarehouseSerializer

    def get_queryset(self):
        return Warehouse.objects.filter(is_active=True)

    @extend_schema(tags=['Inventory - Warehouses'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class WarehouseDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.all()

    @extend_schema(tags=['Inventory - Warehouses'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=['Inventory - Warehouses'])
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)


class StockListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockItemListSerializer

    def get_queryset(self):
        queryset = StockItem.objects.select_related('product', 'warehouse')
        warehouse_id = self.request.query_params.get('warehouse_id')
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if status_filter == 'low':
            queryset = queryset.filter(quantity__gt=0, quantity__lte=models.F('low_stock_threshold'))
        elif status_filter == 'out':
            queryset = queryset.filter(quantity__lte=0)
        elif status_filter == 'in':
            queryset = queryset.filter(quantity__gt=models.F('reserved_quantity'))
        if search:
            queryset = queryset.filter(models.Q(product__name__icontains=search) | models.Q(product__sku__icontains=search))
        return queryset.order_by('-updated_at')

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int), OpenApiParameter('status', str, enum=['low', 'out', 'in']), OpenApiParameter('search', str)], tags=['Inventory - Stock'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class StockDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: StockItemSerializer}, tags=['Inventory - Stock'])
    def get(self, request, product_id):
        try:
            warehouse_id = request.query_params.get('warehouse_id')
            stock = InventoryService.get_stock(product_id, warehouse_id)
            return Response(StockItemSerializer(stock).data)
        except DomainException as e:
            return Response(e.to_dict(), status=status.HTTP_404_NOT_FOUND)


class StockAddView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=StockAddSerializer, responses={200: StockItemSerializer}, tags=['Inventory - Stock'])
    def post(self, request, product_id):
        serializer = StockAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            stock = InventoryService.add_stock(product_id=product_id, quantity=data['quantity'], unit_cost=data.get('unit_cost'), reference=data.get('reference', ''), notes=data.get('notes', ''), user=request.user)
            return Response(StockItemSerializer(stock).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class StockAdjustView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=StockAdjustSerializer, responses={200: StockItemSerializer}, tags=['Inventory - Stock'])
    def post(self, request, product_id):
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            stock = InventoryService.adjust_stock(product_id=product_id, new_quantity=data['quantity'], reason=data.get('reason', ''), notes=data.get('notes', ''), user=request.user)
            return Response(StockItemSerializer(stock).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class StockTransferView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=StockTransferSerializer, responses={200: {'description': 'Transfer successful'}}, tags=['Inventory - Stock'])
    def post(self, request):
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            from_stock, to_stock = InventoryService.transfer_stock(product_id=data['product_id'], from_warehouse_id=data['from_warehouse_id'], to_warehouse_id=data['to_warehouse_id'], quantity=data['quantity'], notes=data.get('notes', ''), user=request.user)
            return Response({'success': True, 'from_stock': StockItemSerializer(from_stock).data, 'to_stock': StockItemSerializer(to_stock).data})
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class LowStockView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockItemListSerializer
    pagination_class = None

    def get_queryset(self):
        warehouse_id = self.request.query_params.get('warehouse_id')
        return InventoryService.get_low_stock_items(warehouse_id)

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int)], tags=['Inventory - Stock'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OutOfStockView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockItemListSerializer
    pagination_class = None

    def get_queryset(self):
        warehouse_id = self.request.query_params.get('warehouse_id')
        return InventoryService.get_out_of_stock_items(warehouse_id)

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int)], tags=['Inventory - Stock'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ReorderView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockItemSerializer
    pagination_class = None

    def get_queryset(self):
        warehouse_id = self.request.query_params.get('warehouse_id')
        return InventoryService.get_reorder_items(warehouse_id)

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int)], tags=['Inventory - Stock'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MovementListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        return InventoryService.get_movements(product_id=self.request.query_params.get('product_id'), warehouse_id=self.request.query_params.get('warehouse_id'), reason=self.request.query_params.get('reason'), reference=self.request.query_params.get('reference'), days=int(self.request.query_params.get('days', 30)))

    @extend_schema(parameters=[OpenApiParameter('product_id', str), OpenApiParameter('warehouse_id', int), OpenApiParameter('reason', str), OpenApiParameter('reference', str), OpenApiParameter('days', int)], tags=['Inventory - Movements'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductMovementView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockMovementSerializer
    pagination_class = None

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        return InventoryService.get_movements(product_id=product_id, days=90)

    @extend_schema(tags=['Inventory - Movements'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AlertListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StockAlertSerializer
    pagination_class = None

    def get_queryset(self):
        warehouse_id = self.request.query_params.get('warehouse_id')
        return InventoryService.get_pending_alerts(warehouse_id)

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int)], tags=['Inventory - Alerts'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AlertResolveView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: StockAlertSerializer}, tags=['Inventory - Alerts'])
    def post(self, request, alert_id):
        notes = request.data.get('notes', '')
        try:
            alert = InventoryService.resolve_alert(alert_id, request.user, notes)
            return Response(StockAlertSerializer(alert).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class InventoryCountListView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = InventoryCountListSerializer

    def get_queryset(self):
        return InventoryCount.objects.all().order_by('-created_at')

    @extend_schema(tags=['Inventory - Counts'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class InventoryCountCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=InventoryCountCreateSerializer, responses={201: InventoryCountSerializer}, tags=['Inventory - Counts'])
    def post(self, request):
        serializer = InventoryCountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count = InventoryService.create_inventory_count(name=data['name'], warehouse_id=data.get('warehouse_id'), product_ids=data.get('product_ids'), notes=data.get('notes', ''), user=request.user)
        return Response(InventoryCountSerializer(count).data, status=status.HTTP_201_CREATED)


class InventoryCountDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: InventoryCountSerializer}, tags=['Inventory - Counts'])
    def get(self, request, count_id):
        try:
            count = InventoryCount.objects.prefetch_related('items__stock__product').get(id=count_id)
            return Response(InventoryCountSerializer(count).data)
        except InventoryCount.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class InventoryCountStartView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: InventoryCountSerializer}, tags=['Inventory - Counts'])
    def post(self, request, count_id):
        try:
            count = InventoryCount.objects.get(id=count_id)
            count.start()
            return Response(InventoryCountSerializer(count).data)
        except InventoryCount.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class InventoryCountCompleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses={200: InventoryCountSerializer}, tags=['Inventory - Counts'])
    def post(self, request, count_id):
        try:
            count = InventoryCount.objects.get(id=count_id)
            apply_adjustments = request.data.get('apply_adjustments', True)
            count.complete(apply_adjustments=apply_adjustments)
            return Response(InventoryCountSerializer(count).data)
        except InventoryCount.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class InventoryCountItemUpdateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(request=InventoryCountItemUpdateSerializer, responses={200: InventoryCountItemSerializer}, tags=['Inventory - Counts'])
    def post(self, request, item_id):
        serializer = InventoryCountItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = InventoryService.update_count_item(count_item_id=item_id, counted_quantity=data['counted_quantity'], notes=data.get('notes', ''), user=request.user)
            return Response(InventoryCountItemSerializer(item).data)
        except DomainException as e:
            return Response(e.to_dict(), status=e.http_status)


class StatisticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int)], responses={200: InventoryStatisticsSerializer}, tags=['Inventory - Statistics'])
    def get(self, request):
        warehouse_id = request.query_params.get('warehouse_id')
        stats = InventoryService.get_statistics(warehouse_id)
        return Response(stats)


class MovementSummaryView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(parameters=[OpenApiParameter('warehouse_id', int), OpenApiParameter('days', int)], tags=['Inventory - Statistics'])
    def get(self, request):
        warehouse_id = request.query_params.get('warehouse_id')
        days = int(request.query_params.get('days', 30))
        summary = InventoryService.get_movement_summary(days, warehouse_id)
        return Response(summary)
