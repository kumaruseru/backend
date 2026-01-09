"""Commerce Orders - Application Services."""
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.core.exceptions import NotFoundError, BusinessRuleViolation, ValidationError
from apps.store.catalog.models import Product
from .models import Order, OrderItem, OrderStatusHistory, OrderNote

logger = logging.getLogger('apps.orders')


class OrderService:
    @classmethod
    @transaction.atomic
    def create_order_from_items(cls, user, items: List[Dict], shipping_info: Dict[str, Any], payment_method: str = Order.PaymentMethod.COD, coupon_code: str = '', customer_note: str = '', source: str = Order.Source.WEB) -> Order:
        if not items:
            raise BusinessRuleViolation(message='No items provided')

        items_data = []
        subtotal = Decimal('0')

        for item in items:
            try:
                product = Product.objects.get(id=item['product_id'], is_active=True)
            except Product.DoesNotExist:
                raise NotFoundError(message='Product not found')

            quantity = item.get('quantity', 1)
            price = product.sale_price if product.sale_price else product.price
            items_data.append({
                'product': product,
                'quantity': quantity,
                'unit_price': price,
                'original_price': product.price if product.sale_price else None
            })
            subtotal += price * quantity

        shipping_fee = Decimal('30000')  # Default shipping fee
        coupon_discount = Decimal('0')
        total = subtotal + shipping_fee - coupon_discount

        order = Order.objects.create(
            user=user,
            source=source,
            recipient_name=shipping_info['recipient_name'],
            phone=shipping_info['phone'],
            email=shipping_info.get('email', user.email),
            address=shipping_info['address'],
            ward=shipping_info['ward'],
            district=shipping_info['district'],
            city=shipping_info['city'],
            district_id=shipping_info.get('district_id'),
            ward_code=shipping_info.get('ward_code', ''),
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount=coupon_discount,
            coupon_code=coupon_code,
            coupon_discount=coupon_discount,
            total=total,
            customer_note=customer_note,
            is_gift=shipping_info.get('is_gift', False),
            gift_message=shipping_info.get('gift_message', '')
        )

        order_items = []
        for item_data in items_data:
            product = item_data['product']
            order_items.append(OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku or '',
                product_image=product.images.first().image.url if product.images.exists() else '',
                product_attributes={},
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                original_price=item_data['original_price']
            ))
        OrderItem.objects.bulk_create(order_items)

        OrderStatusHistory.objects.create(order=order, old_status='', new_status=Order.Status.PENDING, notes='Order created')
        logger.info(f"Order created: {order.order_number}")
        return order

    @staticmethod
    def get_order(order_id: UUID, user=None) -> Order:
        queryset = Order.objects.select_related('user').prefetch_related('items', 'items__product', 'status_history', 'notes')
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(id=order_id)
        except Order.DoesNotExist:
            raise NotFoundError(message='Order not found')

    @staticmethod
    def get_by_order_number(order_number: str, user=None) -> Order:
        queryset = Order.objects.select_related('user').prefetch_related('items', 'status_history')
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        try:
            return queryset.get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundError(message='Order not found')

    @staticmethod
    def get_user_orders(user, status: Optional[str] = None, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        queryset = Order.objects.filter(user=user).prefetch_related('items')
        if status:
            queryset = queryset.filter(status=status)
        total = queryset.count()
        offset = (page - 1) * page_size
        orders = list(queryset[offset:offset + page_size])
        return {'orders': orders, 'total': total, 'page': page, 'page_size': page_size, 'pages': (total + page_size - 1) // page_size}

    @staticmethod
    @transaction.atomic
    def confirm_order(order: Order, admin_user=None) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.confirm(admin_user)
        logger.info(f"Order confirmed: {order.order_number}")
        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order: Order, reason: str = '', cancelled_by=None) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.can_cancel:
            raise BusinessRuleViolation(message='Cannot cancel order in this status')
        order.cancel(reason, cancelled_by)
        logger.info(f"Order cancelled: {order.order_number}")
        return order

    @staticmethod
    def add_note(order: Order, content: str, note_type: str = 'general', created_by=None, is_private: bool = True) -> OrderNote:
        return OrderNote.objects.create(order=order, note_type=note_type, content=content, created_by=created_by, is_private=is_private)

    @staticmethod
    def get_statistics(days: int = 30, user=None) -> Dict[str, Any]:
        from django.db.models import Count, Sum, Avg, Q
        since = timezone.now() - timezone.timedelta(days=days)
        queryset = Order.objects.filter(created_at__gte=since)
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        stats = queryset.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total', filter=Q(status__in=[Order.Status.DELIVERED, Order.Status.COMPLETED])),
            avg_order_value=Avg('total', filter=Q(status__in=[Order.Status.DELIVERED, Order.Status.COMPLETED])),
            pending=Count('id', filter=Q(status=Order.Status.PENDING)),
            confirmed=Count('id', filter=Q(status=Order.Status.CONFIRMED)),
            processing=Count('id', filter=Q(status=Order.Status.PROCESSING)),
            shipping=Count('id', filter=Q(status=Order.Status.SHIPPING)),
            delivered=Count('id', filter=Q(status=Order.Status.DELIVERED)),
            completed=Count('id', filter=Q(status=Order.Status.COMPLETED)),
            cancelled=Count('id', filter=Q(status=Order.Status.CANCELLED)),
            paid_orders=Count('id', filter=Q(payment_status=Order.PaymentStatus.PAID)),
            unpaid_orders=Count('id', filter=Q(payment_status=Order.PaymentStatus.UNPAID)),
            cod_orders=Count('id', filter=Q(payment_method=Order.PaymentMethod.COD)),
            online_orders=Count('id', filter=~Q(payment_method=Order.PaymentMethod.COD))
        )
        total = stats['total_orders'] or 1
        completed = (stats['delivered'] or 0) + (stats['completed'] or 0)
        cancelled = stats['cancelled'] or 0
        return {
            'period_days': days,
            'total_orders': stats['total_orders'] or 0,
            'total_revenue': stats['total_revenue'] or 0,
            'avg_order_value': stats['avg_order_value'] or 0,
            'pending': stats['pending'] or 0,
            'confirmed': stats['confirmed'] or 0,
            'processing': stats['processing'] or 0,
            'shipping': stats['shipping'] or 0,
            'delivered': stats['delivered'] or 0,
            'completed': stats['completed'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'completion_rate': round(completed / total * 100, 2),
            'cancellation_rate': round(cancelled / total * 100, 2),
            'paid_orders': stats['paid_orders'] or 0,
            'unpaid_orders': stats['unpaid_orders'] or 0,
            'cod_orders': stats['cod_orders'] or 0,
            'online_payment_orders': stats['online_orders'] or 0
        }
