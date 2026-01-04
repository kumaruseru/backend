"""
Commerce Orders - Signal Receivers.

Handles events from other modules (Shipping, Billing) in a decoupled way.
Order module decides how to react to external events.
"""
import logging
from django.dispatch import receiver

from apps.commerce.shipping.signals import (
    shipment_status_changed,
    shipment_cancelled,
    cod_collected
)
from .models import Order

logger = logging.getLogger('apps.orders')


# ==================== Shipment Signal Receivers ====================

@receiver(shipment_status_changed)
def sync_order_from_shipment(sender, shipment, old_status, new_status, webhook_data=None, **kwargs):
    """
    Sync order status when shipment status changes.
    
    This keeps the order status logic inside the Order module,
    rather than having Shipping module manipulate orders directly.
    """
    from apps.commerce.shipping.models import Shipment
    
    order = shipment.order
    
    # Mapping: Shipping status -> Order status
    status_transitions = {
        Shipment.Status.PICKED_UP: Order.Status.SHIPPING,
        Shipment.Status.IN_TRANSIT: Order.Status.SHIPPING,
        Shipment.Status.SORTING: Order.Status.SHIPPING,
        Shipment.Status.OUT_FOR_DELIVERY: Order.Status.SHIPPING,
        Shipment.Status.DELIVERED: Order.Status.DELIVERED,
    }
    
    expected_order_status = status_transitions.get(new_status)
    
    if not expected_order_status:
        return  # Unhandled status
    
    if order.status == expected_order_status:
        return  # Already in correct status
    
    try:
        if new_status == Shipment.Status.DELIVERED:
            order.deliver()
            logger.info(f"Order {order.order_number} marked as delivered via shipment signal")
            
            # Handle COD payment
            if order.payment_method == Order.PaymentMethod.COD:
                order.payment_status = Order.PaymentStatus.PAID
                order.save(update_fields=['payment_status', 'updated_at'])
                logger.info(f"Order {order.order_number} COD payment marked as paid")
        
        elif new_status in [Shipment.Status.PICKED_UP, Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY]:
            if order.status == Order.Status.CONFIRMED:
                order.ship(shipment.tracking_code)
                logger.info(f"Order {order.order_number} marked as shipping via shipment signal")
                
    except Exception as e:
        logger.error(f"Failed to sync order {order.order_number} from shipment: {e}")


@receiver(shipment_cancelled)
def handle_shipment_cancellation(sender, shipment, reason='', **kwargs):
    """Handle shipment cancellation - notify admin and may need to create new shipment."""
    order = shipment.order
    
    logger.warning(
        f"Shipment cancelled for order {order.order_number}: {reason}. "
        f"Order status: {order.status}"
    )
    
    # Trigger admin notification via Celery task
    try:
        from apps.users.notifications.tasks import notify_admin_urgent
        notify_admin_urgent.delay(
            title=f"🚨 Đơn vận chuyển bị huỷ: {order.order_number}",
            message=f"""
Đơn hàng: {order.order_number}
Mã vận đơn: {shipment.tracking_code}
Lý do huỷ: {reason or 'Không rõ'}
Trạng thái đơn hàng: {order.get_status_display()}
Khách hàng: {order.recipient_name} - {order.recipient_phone}

Vui lòng kiểm tra và xử lý đơn hàng này.
            """.strip(),
            order_id=str(order.id),
            priority='high'
        )
    except ImportError:
        # Notifications app not available, just log
        logger.warning(f"Cannot notify admin: notifications app not available")


@receiver(cod_collected)
def handle_cod_collection(sender, shipment, amount, **kwargs):
    """Handle COD collection confirmation."""
    order = shipment.order
    
    if order.payment_method == Order.PaymentMethod.COD:
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=['payment_status', 'updated_at'])
        logger.info(f"Order {order.order_number} COD collected: {amount:,.0f}₫")
