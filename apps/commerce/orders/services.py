"""
Commerce Orders - Production-Ready Application Services.

Comprehensive business logic with:
- Order creation from cart or items
- Coupon validation
- Inventory reservation
- Payment integration hooks
- Notification hooks
- Statistics
"""
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.core.exceptions import (
    NotFoundError, BusinessRuleViolation, ValidationError
)
from apps.commerce.shipping.strategies import ShippingStrategyFactory
from apps.store.catalog.models import Product
from apps.commerce.cart.models import Cart
from apps.commerce.gateways.inventory import LocalInventoryGateway
from apps.commerce.orders.interfaces import InventoryGateway
from .models import Order, OrderItem, OrderStatusHistory, OrderNote

logger = logging.getLogger('apps.orders')


class OrderService:
    """
    Order management use cases.
    
    Handles:
    - Order creation
    - Status transitions
    - Payment integration
    - Notifications
    """
    
    # Dependency Injection (Manual for now, can be via Container)
    inventory_gateway: InventoryGateway = LocalInventoryGateway()
    
    @classmethod
    @transaction.atomic
    def create_order_from_cart(
        cls,
        user,
        shipping_info: Dict[str, Any],
        payment_method: str = Order.PaymentMethod.COD,
        coupon_code: str = '',
        customer_note: str = '',
        source: str = Order.Source.WEB,
        ip_address: str = '',
        user_agent: str = ''
    ) -> Order:
        """
        Create order from user's cart (Refactored Composed Method).
        """
        # 1. Validate & Get Cart
        cart = cls._get_validated_cart(user)
        
        # 2. Prepare Items & Validate Stock/Product
        items_data, subtotal = cls._prepare_and_validate_items(cart)
        
        # 3. Calculate Shipping
        shipping_fee = cls._calculate_shipping_fee(
            shipping_info.get('district_id'),
            shipping_info.get('ward_code'),
            subtotal
        )
        
        # 4. Apply Coupon
        coupon, coupon_discount = cls._apply_coupon(coupon_code, user, subtotal)
        
        # 5. Calculate Final Total
        total = subtotal + shipping_fee - coupon_discount
        
        # 6. Persist Order
        order = Order.objects.create(
            user=user,
            source=source,
            # Shipping
            recipient_name=shipping_info['recipient_name'],
            phone=shipping_info['phone'],
            email=shipping_info.get('email', user.email),
            address=shipping_info['address'],
            ward=shipping_info['ward'],
            district=shipping_info['district'],
            city=shipping_info['city'],
            district_id=shipping_info['district_id'],
            ward_code=shipping_info['ward_code'],
            # Payment
            payment_method=payment_method,
            # Amounts
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount=coupon_discount,
            coupon=coupon,
            coupon_code=coupon_code,
            coupon_discount=coupon_discount,
            total=total,
            # Notes
            customer_note=customer_note,
            is_gift=shipping_info.get('is_gift', False),
            gift_message=shipping_info.get('gift_message', ''),
            # Analytics
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # 7. Create Order Items
        cls._create_order_items(order, items_data)
        
        # 8. Reserve Stock & Side Effects
        cls._handle_post_creation_side_effects(order, items_data, coupon, cart, user)
        
        return order

    # --- Composed Steps ---

    @staticmethod
    def _get_validated_cart(user) -> Cart:
        try:
            cart = Cart.objects.prefetch_related('items', 'items__product').get(user=user)
        except Cart.DoesNotExist:
            raise BusinessRuleViolation(message='Giỏ hàng trống')
        
        if not cart.items.exists():
            raise BusinessRuleViolation(message='Giỏ hàng trống')
        return cart

    @classmethod
    def _prepare_and_validate_items(cls, cart: Cart) -> tuple[List[Dict], Decimal]:
        items_data = []
        subtotal = Decimal('0')
        
        # Pre-fetch products to avoid N+1 is handled by prefetch_related in _get_validated_cart
        # But we still iterate
        
        for cart_item in cart.items.all():  # .all() uses prefetch cache
            product = cart_item.product
            
            # Domain Validation
            if not product.is_active:
                raise BusinessRuleViolation(message=f'Sản phẩm "{product.name}" không còn bán')
            
            # Inventory Check via Gateway
            if hasattr(product, 'stock'):
                if not cls.inventory_gateway.check_availability(product.id, cart_item.quantity):
                     raise BusinessRuleViolation(
                        message=f'Sản phẩm "{product.name}" không đủ số lượng trong kho'
                    )
            
            price = product.sale_price or product.price
            items_data.append({
                'product': product,
                'quantity': cart_item.quantity,
                'unit_price': price,
                'original_price': product.price if product.sale_price else None
            })
            subtotal += price * cart_item.quantity
            
        return items_data, subtotal

    @staticmethod
    def _create_order_items(order: Order, items_data: List[Dict]):
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

    @classmethod
    def _handle_post_creation_side_effects(cls, order, items_data, coupon, cart, user):
        # Reserve stock via Gateway
        for item_data in items_data:
            product = item_data['product']
            if hasattr(product, 'stock'):
                cls.inventory_gateway.reserve_stock(
                    product_id=product.id,
                    quantity=item_data['quantity'],
                    reference=order.order_number,
                    user=user
                )
        
        # Use coupon
        if coupon:
            coupon.increment_usage()
        
        # Clear cart
        cart.clear()
        
        # Log History
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status=Order.Status.PENDING,
            notes='Đơn hàng được tạo'
        )
        
        logger.info(f"Order created: {order.order_number} by {user.email}, total: {order.total:,.0f}₫")
        
        # Notify
        cls._notify_order_created(order)

    # --- End Composed Steps ---
    
    @classmethod
    @transaction.atomic
    def create_order_from_items(
        cls,
        user,
        items: List[Dict],
        shipping_info: Dict[str, Any],
        payment_method: str = Order.PaymentMethod.COD,
        coupon_code: str = '',
        customer_note: str = '',
        source: str = Order.Source.WEB
    ) -> Order:
        """
        Create order directly from items (without cart).
        """
        if not items:
            raise BusinessRuleViolation(message='Không có sản phẩm')
        
        items_data = []
        subtotal = Decimal('0')
        
        for item in items:
            try:
                product = Product.objects.get(id=item['product_id'], is_active=True)
            except Product.DoesNotExist:
                raise NotFoundError(message=f'Sản phẩm không tồn tại')
            
            quantity = item.get('quantity', 1)
            
            # Check stock via Gateway
            if hasattr(product, 'stock'):
                if not cls.inventory_gateway.check_availability(product.id, quantity):
                    raise BusinessRuleViolation(
                         message=f'"{product.name}" không đủ số lượng trong kho'
                    )
            
            price = product.sale_price or product.price
            items_data.append({
                'product': product,
                'quantity': quantity,
                'unit_price': price,
                'original_price': product.price if product.sale_price else None
            })
            subtotal += price * quantity
        
        # Calculate shipping
        shipping_fee = cls._calculate_shipping_fee(
            shipping_info.get('district_id'),
            shipping_info.get('ward_code'),
            subtotal
        )
        
        # Apply coupon
        coupon = None
        coupon_discount = Decimal('0')
        if coupon_code:
            coupon, coupon_discount = cls._apply_coupon(
                coupon_code, user, subtotal
            )
        
        total = subtotal + shipping_fee - coupon_discount
        
        # Create order
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
            district_id=shipping_info['district_id'],
            ward_code=shipping_info['ward_code'],
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount=coupon_discount,
            coupon=coupon,
            coupon_code=coupon_code,
            coupon_discount=coupon_discount,
            total=total,
            customer_note=customer_note,
            is_gift=shipping_info.get('is_gift', False),
            gift_message=shipping_info.get('gift_message', '')
        )
        
        # Create items
        cls._create_order_items(order, items_data)
        
        # Reserve stock via Gateway (Manual handling here as we don't have cart side effects)
        for item_data in items_data:
            product = item_data['product']
            if hasattr(product, 'stock'):
                cls.inventory_gateway.reserve_stock(
                    product_id=product.id,
                    quantity=item_data['quantity'],
                    reference=order.order_number,
                    user=user
                )
        
        if coupon:
            coupon.increment_usage()
        
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status=Order.Status.PENDING,
            notes='Đơn hàng được tạo'
        )
        
        logger.info(f"Order created: {order.order_number}")
        cls._notify_order_created(order)
        
        return order
    
    # --- Query Methods ---
    
    @staticmethod
    def get_order(order_id: UUID, user=None) -> Order:
        """Get order by ID."""
        queryset = Order.objects.select_related('user', 'coupon').prefetch_related(
            'items', 'items__product', 'status_history', 'notes'
        )
        
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        try:
            return queryset.get(id=order_id)
        except Order.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy đơn hàng')
    
    @staticmethod
    def get_by_order_number(order_number: str, user=None) -> Order:
        """Get order by order number."""
        queryset = Order.objects.select_related('user').prefetch_related(
            'items', 'status_history'
        )
        
        if user and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        try:
            return queryset.get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundError(message='Không tìm thấy đơn hàng')
    
    @staticmethod
    def get_user_orders(
        user,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get paginated orders for a user."""
        queryset = Order.objects.filter(user=user).prefetch_related('items')
        
        if status:
            queryset = queryset.filter(status=status)
        
        total = queryset.count()
        offset = (page - 1) * page_size
        orders = list(queryset[offset:offset + page_size])
        
        return {
            'orders': orders,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': (total + page_size - 1) // page_size
        }
    
    # --- Status Operations ---
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order: Order, admin_user=None) -> Order:
        """Confirm a pending order with row lock."""
        # Lock the row to prevent race conditions
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.confirm(admin_user)
        logger.info(f"Order confirmed: {order.order_number}")
        OrderService._notify_order_confirmed(order)
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(
        order: Order,
        reason: str = '',
        cancelled_by=None
    ) -> Order:
        """Cancel an order with row lock."""
        # Lock the row to prevent race conditions
        order = Order.objects.select_for_update().get(pk=order.pk)
        
        if not order.can_cancel:
            raise BusinessRuleViolation(
                message='Không thể hủy đơn hàng ở trạng thái này'
            )
        
        order.cancel(reason, cancelled_by)
        
        logger.info(f"Order cancelled: {order.order_number}")
        OrderService._notify_order_cancelled(order)
        
        return order
    
    @staticmethod
    @transaction.atomic
    def reorder(original_order: Order, user) -> Order:
        """Create new order from previous order."""
        if original_order.user != user:
            raise BusinessRuleViolation(message='Không có quyền đặt lại đơn này')
        
        items = []
        for item in original_order.items.all():
            if item.product and item.product.is_active:
                items.append({
                    'product_id': item.product.id,
                    'quantity': item.quantity
                })
        
        if not items:
            raise BusinessRuleViolation(
                message='Không có sản phẩm nào còn bán có thể đặt lại'
            )
        
        # Get user's default address
        default_address = user.addresses.filter(is_default=True).first()
        if not default_address:
            raise BusinessRuleViolation(
                message='Vui lòng thêm địa chỉ giao hàng'
            )
        
        shipping_info = {
            'recipient_name': default_address.full_name,
            'phone': default_address.phone,
            'email': user.email,
            'address': default_address.street_address,
            'ward': default_address.ward,
            'district': default_address.district,
            'city': default_address.city,
            'district_id': default_address.district_id,
            'ward_code': default_address.ward_code
        }
        
        return OrderService.create_order_from_items(
            user=user,
            items=items,
            shipping_info=shipping_info,
            payment_method=original_order.payment_method,
            source=Order.Source.WEB
        )
    
    # --- Notes ---
    
    @staticmethod
    def add_note(
        order: Order,
        content: str,
        note_type: str = 'general',
        created_by=None,
        is_private: bool = True
    ) -> OrderNote:
        """Add note to order."""
        return OrderNote.objects.create(
            order=order,
            note_type=note_type,
            content=content,
            created_by=created_by,
            is_private=is_private
        )
    
    # --- Statistics ---
    
    @staticmethod
    def get_statistics(
        days: int = 30,
        user=None
    ) -> Dict[str, Any]:
        """Get order statistics."""
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
    
    # --- Internal Methods ---
    
    @staticmethod
    def _calculate_shipping_fee(
        district_id: int,
        ward_code: str,
        subtotal: Decimal
    ) -> Decimal:
        """Calculate shipping fee using Strategy."""
        provider = getattr(settings, 'DEFAULT_SHIPPING_PROVIDER', 'ghn')
        strategy = ShippingStrategyFactory.get_strategy(provider)
        
        return strategy.calculate(
            subtotal=subtotal,
            district_id=district_id,
            ward_code=ward_code,
            weight=500  # Default weight
        )
    
    @staticmethod
    def _apply_coupon(
        coupon_code: str,
        user,
        subtotal: Decimal
    ) -> tuple:
        """Validate and calculate coupon discount."""
        try:
            from apps.store.marketing.models import Coupon
            
            coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
            
            if not coupon.is_valid:
                raise BusinessRuleViolation(
                    message='Mã giảm giá đã hết hạn hoặc không hợp lệ'
                )
            
            if subtotal < coupon.minimum_amount:
                raise BusinessRuleViolation(
                    message=f'Đơn hàng tối thiểu {coupon.minimum_amount:,.0f}₫'
                )
            
            discount = coupon.calculate_discount(subtotal)
            return coupon, discount
            
        except Coupon.DoesNotExist:
            raise BusinessRuleViolation(message='Mã giảm giá không tồn tại')
    
    # --- Notifications ---
    
    @staticmethod
    def _notify_order_created(order: Order) -> None:
        """Send order created notification."""
        try:
            from apps.users.notifications.services import EmailService
            # TODO: Implement order confirmation email
            logger.debug(f"Order created notification for {order.order_number}")
        except Exception as e:
            logger.warning(f"Failed to send order created notification: {e}")
    
    @staticmethod
    def _notify_order_confirmed(order: Order) -> None:
        """Send order confirmed notification."""
        try:
            from apps.users.notifications.services import EmailService
            logger.debug(f"Order confirmed notification for {order.order_number}")
        except Exception as e:
            logger.warning(f"Failed to send order confirmed notification: {e}")
    
    @staticmethod
    def _notify_order_cancelled(order: Order) -> None:
        """Send order cancelled notification."""
        try:
            from apps.users.notifications.services import EmailService
            logger.debug(f"Order cancelled notification for {order.order_number}")
        except Exception as e:
            logger.warning(f"Failed to send order cancelled notification: {e}")
