"""Commerce Shipping - Signal Handlers.

Shipment status tracking and notifications.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger('apps.shipping.signals')


@receiver(pre_save, sender='shipping.Shipment')
def on_shipment_status_changing(sender, instance, **kwargs):
    """Track shipment status changes."""
    if not instance.pk:
        return
    
    try:
        original = sender.objects.filter(pk=instance.pk).only('status').first()
        if original and original.status != instance.status:
            instance._status_changed = True
            instance._old_status = original.status
            instance._new_status = instance.status
    except Exception as e:
        logger.warning(f"Error tracking shipment status: {e}")


@receiver(post_save, sender='shipping.Shipment')
def on_shipment_saved(sender, instance, created, **kwargs):
    """Handle shipment creation and status changes."""
    try:
        if created:
            # Create initial shipment event
            _create_shipment_event(instance, 'Shipment created')
            logger.info(f"Shipment {instance.tracking_code} created for order {instance.order.order_number}")
            return
        
        if not getattr(instance, '_status_changed', False):
            return
        
        old_status = instance._old_status
        new_status = instance._new_status
        
        # Create status change event
        _create_shipment_event(instance, f"Status changed from {old_status} to {new_status}")
        
        # Send notifications based on status
        if new_status == 'picked_up':
            _send_shipment_notification(instance, 'shipment_picked_up')
            
        elif new_status == 'in_transit':
            _send_shipment_notification(instance, 'shipment_in_transit')
            
        elif new_status == 'out_for_delivery':
            _send_shipment_notification(instance, 'out_for_delivery')
            
        elif new_status == 'delivered':
            _send_shipment_notification(instance, 'shipment_delivered')
            # Update order status
            _update_order_on_delivery(instance)
            
        elif new_status == 'failed':
            _send_shipment_notification(instance, 'delivery_failed')
            
        elif new_status == 'returned':
            _send_shipment_notification(instance, 'shipment_returned')
        
        # Cleanup
        if hasattr(instance, '_status_changed'):
            del instance._status_changed
            del instance._old_status
            del instance._new_status
            
    except Exception as e:
        logger.warning(f"Error processing shipment signal: {e}")


@receiver(post_save, sender='shipping.ShipmentEvent')
def on_shipment_event_created(sender, instance, created, **kwargs):
    """Update shipment location and status from events."""
    if not created:
        return
    
    try:
        shipment = instance.shipment
        if instance.location:
            shipment.last_location = instance.location
        shipment.last_status_update = instance.occurred_at
        shipment.save(update_fields=['last_location', 'last_status_update', 'updated_at'])
    except Exception as e:
        logger.warning(f"Error updating shipment from event: {e}")


def _create_shipment_event(shipment, description, location=''):
    """Create a shipment tracking event."""
    try:
        from .models import ShipmentEvent
        ShipmentEvent.objects.create(
            shipment=shipment,
            status=shipment.status,
            description=description,
            location=location or shipment.last_location or '',
            occurred_at=timezone.now()
        )
    except Exception as e:
        logger.debug(f"Could not create shipment event: {e}")


def _update_order_on_delivery(shipment):
    """Update order status when shipment is delivered."""
    try:
        order = shipment.order
        if order.status in ['shipping', 'ready_to_ship']:
            order.status = 'delivered'
            order.delivered_at = timezone.now()
            order.save(update_fields=['status', 'delivered_at', 'updated_at'])
            
            # Handle COD payment
            if order.payment_method == 'cod' and shipment.cod_amount > 0:
                order.payment_status = 'paid'
                order.paid_at = timezone.now()
                order.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
                
    except Exception as e:
        logger.warning(f"Error updating order on delivery: {e}")


def _send_shipment_notification(shipment, notification_type):
    """Send shipment notification to customer."""
    order = shipment.order
    if not order or not order.user:
        return
    
    try:
        from apps.users.notifications.services import NotificationService
        
        messages = {
            'shipment_picked_up': f"Your order #{order.order_number} has been picked up by {shipment.get_provider_display()}.",
            'shipment_in_transit': f"Your order #{order.order_number} is on its way!",
            'out_for_delivery': f"Your order #{order.order_number} is out for delivery today!",
            'shipment_delivered': f"Your order #{order.order_number} has been delivered.",
            'delivery_failed': f"Delivery attempt for order #{order.order_number} was unsuccessful.",
            'shipment_returned': f"Your order #{order.order_number} is being returned.",
        }
        
        NotificationService.create(
            user=order.user,
            notification_type=notification_type,
            title='Shipping Update',
            message=messages.get(notification_type, f"Update for order #{order.order_number}"),
            data={
                'order_id': str(order.id),
                'order_number': order.order_number,
                'tracking_code': shipment.tracking_code,
                'shipment_status': shipment.status,
            }
        )
    except Exception as e:
        logger.debug(f"Could not send shipment notification: {e}")
