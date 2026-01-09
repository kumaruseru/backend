"""Store Inventory - Application Services."""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta

from apps.common.core.exceptions import NotFoundError, ValidationError, BusinessRuleViolation
from .models import Warehouse, StockItem, StockMovement, StockAlert, InventoryCount, InventoryCountItem
from apps.store.catalog.services import CatalogService

logger = logging.getLogger('apps.inventory')


class InventoryService:
    @staticmethod
    def get_stock(product_id: UUID, warehouse_id: int = None) -> StockItem:
        queryset = StockItem.objects.select_related('product', 'warehouse')
        try:
            if warehouse_id:
                return queryset.get(product_id=product_id, warehouse_id=warehouse_id)
            return queryset.get(product_id=product_id)
        except StockItem.DoesNotExist:
            raise NotFoundError(message='Stock not found')

    @staticmethod
    def check_stock_availability(product_id: UUID, quantity: int, warehouse_id: int = None) -> bool:
        try:
            stock = InventoryService.get_stock(product_id, warehouse_id)
            return stock.available_quantity >= quantity
        except NotFoundError:
            return False

    @staticmethod
    def get_or_create_stock(product_id: UUID, warehouse_id: int = None) -> StockItem:
        defaults = {'quantity': 0}
        if warehouse_id:
            defaults['warehouse_id'] = warehouse_id
        stock, created = StockItem.objects.get_or_create(product_id=product_id, warehouse_id=warehouse_id, defaults=defaults)
        if created:
            logger.info(f"Created stock item for product {product_id}")
        return stock

    @staticmethod
    @transaction.atomic
    def add_stock(product_id: UUID, quantity: int, unit_cost: Decimal = None, reference: str = '', notes: str = '', warehouse_id: int = None, user=None) -> StockItem:
        stock = InventoryService.get_or_create_stock(product_id, warehouse_id)
        stock.add_stock(quantity, reference, notes, unit_cost, user)
        logger.info(f"Added {quantity} units to product {product_id}")
        return stock

    @staticmethod
    @transaction.atomic
    def adjust_stock(product_id: UUID, new_quantity: int, reason: str = '', notes: str = '', warehouse_id: int = None, user=None) -> StockItem:
        stock = InventoryService.get_stock(product_id, warehouse_id)
        old_quantity = stock.quantity
        stock.adjust_stock(new_quantity, reason, notes, user)
        logger.info(f"Adjusted stock for product {product_id}: {old_quantity} -> {new_quantity}")
        return stock

    @staticmethod
    @transaction.atomic
    def reserve_stock(product_id: UUID, quantity: int, reference: str, warehouse_id: int = None, user=None) -> bool:
        try:
            stock = InventoryService.get_stock(product_id, warehouse_id)
        except NotFoundError:
            return False
        return stock.reserve(quantity, reference, user)

    @staticmethod
    @transaction.atomic
    def release_stock(product_id: UUID, quantity: int, reference: str, warehouse_id: int = None, user=None) -> int:
        try:
            stock = InventoryService.get_stock(product_id, warehouse_id)
        except NotFoundError:
            return 0
        return stock.release(quantity, reference, user)

    @staticmethod
    @transaction.atomic
    def confirm_sale(product_id: UUID, quantity: int, reference: str, warehouse_id: int = None, user=None) -> None:
        stock = InventoryService.get_stock(product_id, warehouse_id)
        stock.confirm_sale(quantity, reference, user)
        CatalogService.increment_product_sold_count(stock.product_id, quantity)

    @staticmethod
    @transaction.atomic
    def process_return(product_id: UUID, quantity: int, reference: str, warehouse_id: int = None, user=None) -> StockItem:
        stock = InventoryService.get_stock(product_id, warehouse_id)
        stock.process_return(quantity, reference, user)
        logger.info(f"Processed return of {quantity} units for product {product_id}")
        return stock

    @staticmethod
    @transaction.atomic
    def transfer_stock(product_id: UUID, from_warehouse_id: int, to_warehouse_id: int, quantity: int, notes: str = '', user=None) -> tuple:
        from_stock = InventoryService.get_stock(product_id, from_warehouse_id)
        if from_stock.available_quantity < quantity:
            raise BusinessRuleViolation(message=f'Insufficient stock. Available: {from_stock.available_quantity}')
        to_stock = InventoryService.get_or_create_stock(product_id, to_warehouse_id)
        old_from = from_stock.quantity
        from_stock.quantity -= quantity
        from_stock.save(update_fields=['quantity', 'updated_at'])
        StockMovement.objects.create(stock=from_stock, movement_type=StockMovement.Type.TRANSFER, quantity_change=-quantity, quantity_before=old_from, quantity_after=from_stock.quantity, reason=StockMovement.Reason.TRANSFER_OUT, reference=f'TO:{to_warehouse_id}', notes=notes, created_by=user)
        old_to = to_stock.quantity
        to_stock.quantity += quantity
        to_stock.save(update_fields=['quantity', 'updated_at'])
        StockMovement.objects.create(stock=to_stock, movement_type=StockMovement.Type.TRANSFER, quantity_change=quantity, quantity_before=old_to, quantity_after=to_stock.quantity, reason=StockMovement.Reason.TRANSFER_IN, reference=f'FROM:{from_warehouse_id}', notes=notes, created_by=user)
        logger.info(f"Transferred {quantity} units of product {product_id}")
        return from_stock, to_stock

    @staticmethod
    def get_low_stock_items(warehouse_id: int = None, limit: int = 50) -> list:
        queryset = StockItem.objects.select_related('product', 'warehouse').filter(product__is_active=True, quantity__gt=0, quantity__lte=F('low_stock_threshold'))
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        return list(queryset.order_by('quantity')[:limit])

    @staticmethod
    def get_out_of_stock_items(warehouse_id: int = None, limit: int = 50) -> list:
        queryset = StockItem.objects.select_related('product', 'warehouse').filter(product__is_active=True, quantity__lte=0)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        return list(queryset[:limit])

    @staticmethod
    def get_reorder_items(warehouse_id: int = None) -> list:
        queryset = StockItem.objects.select_related('product', 'warehouse').filter(product__is_active=True, quantity__lte=F('reorder_point'))
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        return list(queryset.order_by('quantity'))

    @staticmethod
    def get_movements(product_id: UUID = None, warehouse_id: int = None, reason: str = None, reference: str = None, days: int = 30, limit: int = 100) -> list:
        since = timezone.now() - timedelta(days=days)
        queryset = StockMovement.objects.select_related('stock__product', 'created_by').filter(created_at__gte=since)
        if product_id:
            queryset = queryset.filter(stock__product_id=product_id)
        if warehouse_id:
            queryset = queryset.filter(stock__warehouse_id=warehouse_id)
        if reason:
            queryset = queryset.filter(reason=reason)
        if reference:
            queryset = queryset.filter(reference__icontains=reference)
        return list(queryset.order_by('-created_at')[:limit])

    @staticmethod
    def get_pending_alerts(warehouse_id: int = None, limit: int = 50) -> list:
        queryset = StockAlert.objects.select_related('stock__product').filter(is_resolved=False)
        if warehouse_id:
            queryset = queryset.filter(stock__warehouse_id=warehouse_id)
        return list(queryset.order_by('-created_at')[:limit])

    @staticmethod
    def resolve_alert(alert_id: int, user=None, notes: str = '') -> StockAlert:
        try:
            alert = StockAlert.objects.get(id=alert_id)
        except StockAlert.DoesNotExist:
            raise NotFoundError(message='Alert not found')
        alert.resolve(user, notes)
        return alert

    @staticmethod
    @transaction.atomic
    def create_inventory_count(name: str, warehouse_id: int = None, product_ids: list = None, notes: str = '', user=None) -> InventoryCount:
        count = InventoryCount.objects.create(name=name, warehouse_id=warehouse_id, notes=notes, created_by=user)
        queryset = StockItem.objects.select_related('product')
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if product_ids:
            queryset = queryset.filter(product_id__in=product_ids)
        for stock in queryset:
            InventoryCountItem.objects.create(inventory_count=count, stock=stock, system_quantity=stock.quantity)
        logger.info(f"Created inventory count: {count.id}")
        return count

    @staticmethod
    def update_count_item(count_item_id: int, counted_quantity: int, notes: str = '', user=None) -> InventoryCountItem:
        try:
            item = InventoryCountItem.objects.get(id=count_item_id)
        except InventoryCountItem.DoesNotExist:
            raise NotFoundError(message='Item not found')
        item.counted_quantity = counted_quantity
        item.notes = notes
        item.counted_by = user
        item.counted_at = timezone.now()
        item.save()
        return item

    @staticmethod
    def get_statistics(warehouse_id: int = None) -> Dict[str, Any]:
        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        queryset = StockItem.objects.filter(product__is_active=True)
        movements_today = StockMovement.objects.filter(created_at__gte=today_start)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
            movements_today = movements_today.filter(stock__warehouse_id=warehouse_id)
        total_value = sum((item.unit_cost or item.product.price) * item.quantity for item in queryset.select_related('product'))
        stats = queryset.aggregate(total_products=Count('id'), in_stock=Count('id', filter=Q(quantity__gt=F('reserved_quantity'))), low_stock=Count('id', filter=Q(quantity__gt=0, quantity__lte=F('low_stock_threshold'))), out_of_stock=Count('id', filter=Q(quantity__lte=0)))
        movement_stats = movements_today.aggregate(movements_today=Count('id'), items_sold=Sum('quantity_change', filter=Q(reason='sale')), items_received=Sum('quantity_change', filter=Q(reason='purchase')))
        pending_alerts = StockAlert.objects.filter(is_resolved=False)
        if warehouse_id:
            pending_alerts = pending_alerts.filter(stock__warehouse_id=warehouse_id)
        return {
            'total_products': stats['total_products'] or 0,
            'total_stock_value': total_value,
            'in_stock_count': stats['in_stock'] or 0,
            'low_stock_count': stats['low_stock'] or 0,
            'out_of_stock_count': stats['out_of_stock'] or 0,
            'pending_alerts': pending_alerts.count(),
            'movements_today': movement_stats['movements_today'] or 0,
            'items_sold_today': abs(movement_stats['items_sold'] or 0),
            'items_received_today': movement_stats['items_received'] or 0
        }

    @staticmethod
    def get_movement_summary(days: int = 30, warehouse_id: int = None) -> Dict[str, Any]:
        since = timezone.now() - timedelta(days=days)
        queryset = StockMovement.objects.filter(created_at__gte=since)
        if warehouse_id:
            queryset = queryset.filter(stock__warehouse_id=warehouse_id)
        summary = queryset.values('reason').annotate(count=Count('id'), total_quantity=Sum('quantity_change')).order_by('reason')
        return {'period_days': days, 'by_reason': list(summary), 'total_movements': queryset.count()}
