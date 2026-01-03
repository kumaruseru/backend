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
from apps.store.catalog.models import Product
from apps.commerce.cart.models import Cart
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
    
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(
        user,
        shipping_info: Dict[str, Any],
        payment_method: str = 'cod',
        coupon_code: str = '',
        customer_note: str = '',
        source: str = 'web',
        ip_address: str = '',
        user_agent: str = ''
    ) -> Order:
        """
        Create order from user's cart.
        
        Args:
            user: Authenticated user
            shipping_info: Recipient, address, phone, etc.
            payment_method: Payment method code
            coupon_code: Optional coupon code
            customer_note: Customer notes
            source: Order source (web, mobile, api)
            ip_address: Client IP
            user_agent: Client user agent
            
        Returns:
            Created Order
        """
        # Get cart
        try:
            cart = Cart.objects.prefetch_related(
                'items', 'items__product'
            ).get(user=user)
        except Cart.DoesNotExist:
            raise BusinessRuleViolation(message='Giỏ hàng trống')
        
        if not cart.items.exists():
            raise BusinessRuleViolation(message='Giỏ hàng trống')
        
        # Validate items and calculate totals
        items_data = []
        subtotal = Decimal('0')
        
        for cart_item in cart.items.select_related('product'):
            product = cart_item.product
            
            if not product.is_active:
                raise BusinessRuleViolation(
                    message=f'Sản phẩm "{product.name}" không còn bán'
                )
            
            # Check stock with row lock to prevent race condition
            if hasattr(product, 'stock'):
                from apps.store.inventory.models import ProductStock
                stock = ProductStock.objects.select_for_update().get(product=product)
                available = stock.available_quantity
                if cart_item.quantity > available:
                    raise BusinessRuleViolation(
                        message=f'Sản phẩm "{product.name}" chỉ còn {available} trong kho'
                    )
            
            price = product.sale_price or product.price
            items_data.append({
                'product': product,
                'quantity': cart_item.quantity,
                'unit_price': price,
                'original_price': product.price if product.sale_price else None
            })
            subtotal += price * cart_item.quantity
        
        # Calculate shipping fee
        shipping_fee = OrderService._calculate_shipping_fee(
            shipping_info.get('district_id'),
            shipping_info.get('ward_code'),
            subtotal
        )
        
        # Apply coupon
        coupon = None
        coupon_discount = Decimal('0')
        if coupon_code:
            coupon, coupon_discount = OrderService._apply_coupon(
                coupon_code, user, subtotal
            )
        
        # Calculate total
        total = subtotal + shipping_fee - coupon_discount
        
        # Create order
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
        
        # Create order items using bulk_create for performance
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
        
        # Reserve stock
        for item_data in items_data:
            product = item_data['product']
            if hasattr(product, 'stock'):
                product.stock.reserve(item_data['quantity'], order.order_number)
        
        # Use coupon
        if coupon:
            coupon.increment_usage()
        
        # Clear cart
        cart.clear()
        
        # Log
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status=Order.Status.PENDING,
            notes='Đơn hàng được tạo'
        )
        
        logger.info(
            f"Order created: {order.order_number} by {user.email}, "
            f"total: {total:,.0f}₫"
        )
        
        # Notify
        OrderService._notify_order_created(order)
        
        return order
    
    @staticmethod
    @transaction.atomic
    def create_order_from_items(
        user,
        items: List[Dict],
        shipping_info: Dict[str, Any],
        payment_method: str = 'cod',
        coupon_code: str = '',
        customer_note: str = '',
        source: str = 'web'
    ) -> Order:
        """
        Create order directly from items (without cart).
        
        For quick buy / reorder functionality.
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
            
            # Check stock
            if hasattr(product, 'stock'):
                available = product.stock.available_quantity
                if quantity > available:
                    raise BusinessRuleViolation(
                        message=f'"{product.name}" chỉ còn {available} trong kho'
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
        shipping_fee = OrderService._calculate_shipping_fee(
            shipping_info.get('district_id'),
            shipping_info.get('ward_code'),
            subtotal
        )
        
        # Apply coupon
        coupon = None
        coupon_discount = Decimal('0')
        if coupon_code:
            coupon, coupon_discount = OrderService._apply_coupon(
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
        for item_data in items_data:
            product = item_data['product']
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku or '',
                product_image=product.images.first().image.url if product.images.exists() else '',
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                original_price=item_data['original_price']
            )
            
            if hasattr(product, 'stock'):
                product.stock.reserve(item_data['quantity'], order.order_number)
        
        if coupon:
            coupon.increment_usage()
        
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status=Order.Status.PENDING,
            notes='Đơn hàng được tạo'
        )
        
        logger.info(f"Order created: {order.order_number}")
        OrderService._notify_order_created(order)
        
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
        """Confirm a pending order."""
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
        """Cancel an order."""
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
            source='web'
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
            total_revenue=Sum('total', filter=Q(status__in=['delivered', 'completed'])),
            avg_order_value=Avg('total', filter=Q(status__in=['delivered', 'completed'])),
            pending=Count('id', filter=Q(status='pending')),
            confirmed=Count('id', filter=Q(status='confirmed')),
            processing=Count('id', filter=Q(status='processing')),
            shipping=Count('id', filter=Q(status='shipping')),
            delivered=Count('id', filter=Q(status='delivered')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            paid_orders=Count('id', filter=Q(payment_status='paid')),
            unpaid_orders=Count('id', filter=Q(payment_status='unpaid')),
            cod_orders=Count('id', filter=Q(payment_method='cod')),
            online_orders=Count('id', filter=~Q(payment_method='cod'))
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
        """Calculate shipping fee using GHN."""
        # Free shipping for orders over threshold
        free_shipping_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', 500000)
        if subtotal >= free_shipping_threshold:
            return Decimal('0')
        
        try:
            from apps.commerce.shipping.services import GHNService
            ghn = GHNService()
            result = ghn.calculate_fee(
                to_district_id=district_id,
                to_ward_code=ward_code,
                weight=500
            )
            if result.get('success'):
                return Decimal(result.get('total', 30000))
            else:
                error_msg = result.get('error', 'Không thể tính phí vận chuyển')
                logger.error(f"GHN fee calculation failed: {error_msg}")
                raise BusinessRuleViolation(
                    message=f'Không thể tính phí vận chuyển: {error_msg}. Vui lòng thử lại.'
                )
        except BusinessRuleViolation:
            raise
        except Exception as e:
            logger.error(f"Shipping fee calculation failed: {e}")
            # Alert admins if GHN is down
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"GHN API Down - Shipping fee calculation failed: {e}",
                    level="error"
                )
            except Exception:
                pass
            raise BusinessRuleViolation(
                message='Hệ thống vận chuyển tạm thời không khả dụng. Vui lòng thử lại sau.'
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
