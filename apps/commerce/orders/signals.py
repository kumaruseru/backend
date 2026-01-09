"""Commerce Orders - Signal Handlers.

Order lifecycle events, inventory updates, and notifications.
"""
import logging
import django.dispatch
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('apps.orders.signals')

# Custom signals for order lifecycle events
order_created = django.dispatch.Signal()
order_confirmed = django.dispatch.Signal()
order_cancelled = django.dispatch.Signal()
order_shipped = django.dispatch.Signal()
order_delivered = django.dispatch.Signal()
order_completed = django.dispatch.Signal()


@receiver(post_save, sender='orders.Order')
def on_order_saved(sender, instance, created, **kwargs):
    """Handle order creation and status changes."""
    try:
        if created:
            # Send order created signal
            order_created.send(sender=sender, order=instance)
            
            # Reserve inventory for order items
            _reserve_inventory_for_order(instance)
            
            # Send order confirmation notification
            _send_order_notification(instance, 'order_created')
            
            logger.info(f"Order {instance.order_number} created")
            
    except Exception as e:
        logger.warning(f"Error processing order creation signal: {e}")


@receiver(pre_save, sender='orders.Order')
def on_order_status_changing(sender, instance, **kwargs):
    """Track order status changes and trigger appropriate actions."""
    if not instance.pk:
        return
    
    try:
        original = sender.objects.filter(pk=instance.pk).only('status').first()
        if not original:
            return
        
        old_status = original.status
        new_status = instance.status
        
        if old_status != new_status:
            instance._status_changed = True
            instance._old_status = old_status
            instance._new_status = new_status
            
    except Exception as e:
        logger.warning(f"Error tracking order status change: {e}")


@receiver(post_save, sender='orders.Order')
def on_order_status_changed(sender, instance, created, **kwargs):
    """Handle order status transitions."""
    if created:
        return
    
    if not getattr(instance, '_status_changed', False):
        return
    
    try:
        old_status = instance._old_status
        new_status = instance._new_status
        
        logger.info(f"Order {instance.order_number} status: {old_status} → {new_status}")
        
        # Handle specific transitions
        if new_status == 'confirmed':
            order_confirmed.send(sender=sender, order=instance)
            _send_order_notification(instance, 'order_confirmed')
            
        elif new_status == 'cancelled':
            order_cancelled.send(sender=sender, order=instance)
            _release_inventory_for_order(instance)
            _send_order_notification(instance, 'order_cancelled')
            
        elif new_status == 'shipping':
            order_shipped.send(sender=sender, order=instance)
            _send_order_notification(instance, 'order_shipped')
            
        elif new_status == 'delivered':
            order_delivered.send(sender=sender, order=instance)
            _confirm_inventory_sale(instance)
            _send_order_notification(instance, 'order_delivered')
            
        elif new_status == 'completed':
            order_completed.send(sender=sender, order=instance)
            _send_order_notification(instance, 'order_completed')
            
        # Clean up temporary attributes
        del instance._status_changed
        del instance._old_status
        del instance._new_status
        
    except Exception as e:
        logger.warning(f"Error processing order status change: {e}")


def _reserve_inventory_for_order(order):
    """Reserve inventory for all items in an order."""
    try:
        from apps.store.inventory.services import InventoryService
        
        for item in order.items.all():
            if item.product_id:
                success = InventoryService.reserve_stock(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    reference=order.order_number
                )
                if not success:
                    logger.warning(f"Could not reserve stock for product {item.product_id}")
                    
    except Exception as e:
        logger.warning(f"Error reserving inventory for order {order.order_number}: {e}")


def _release_inventory_for_order(order):
    """Release reserved inventory when order is cancelled."""
    try:
        from apps.store.inventory.services import InventoryService
        
        for item in order.items.all():
            if item.product_id:
                InventoryService.release_stock(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    reference=order.order_number
                )
                
    except Exception as e:
        logger.warning(f"Error releasing inventory for order {order.order_number}: {e}")


def _confirm_inventory_sale(order):
    """Confirm inventory sale when order is delivered."""
    try:
        from apps.store.inventory.services import InventoryService
        
        for item in order.items.all():
            if item.product_id:
                InventoryService.confirm_sale(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    reference=order.order_number
                )
                
    except Exception as e:
        logger.warning(f"Error confirming inventory sale for order {order.order_number}: {e}")


def _send_order_notification(order, notification_type):
    """Send order-related notification to customer."""
    if not order.user:
        return
    
    try:
        from apps.users.notifications.services import NotificationService
        
        titles = {
            'order_created': 'Order Placed Successfully',
            'order_confirmed': 'Order Confirmed',
            'order_cancelled': 'Order Cancelled',
            'order_shipped': 'Order Shipped',
            'order_delivered': 'Order Delivered',
            'order_completed': 'Order Completed',
        }
        
        messages = {
            'order_created': f"Your order #{order.order_number} has been placed.",
            'order_confirmed': f"Your order #{order.order_number} has been confirmed.",
            'order_cancelled': f"Your order #{order.order_number} has been cancelled.",
            'order_shipped': f"Your order #{order.order_number} is on its way!",
            'order_delivered': f"Your order #{order.order_number} has been delivered.",
            'order_completed': f"Your order #{order.order_number} is complete. Thank you!",
        }
        
        NotificationService.create(
            user=order.user,
            notification_type=notification_type,
            title=titles.get(notification_type, 'Order Update'),
            message=messages.get(notification_type, f"Order #{order.order_number} updated."),
            data={
                'order_id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
            }
        )
    except Exception as e:
        logger.debug(f"Could not send order notification: {e}")
