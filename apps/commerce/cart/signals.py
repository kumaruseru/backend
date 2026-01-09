"""Commerce Cart - Signal Handlers.

Cart lifecycle events and abandoned cart tracking.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('apps.cart.signals')


@receiver(post_save, sender='cart.Cart')
def on_cart_saved(sender, instance, created, **kwargs):
    """Track cart creation and updates."""
    try:
        if created:
            logger.debug(f"New cart created: {instance.id}")
            # Log cart creation event
            _log_cart_event(instance, 'created')
        else:
            # Update last activity timestamp handled in model
            pass
    except Exception as e:
        logger.warning(f"Error processing cart signal: {e}")


@receiver(post_save, sender='cart.CartItem')
def on_cart_item_saved(sender, instance, created, **kwargs):
    """Handle cart item changes - update cart totals and track events."""
    try:
        cart = instance.cart
        
        if created:
            _log_cart_event(cart, 'item_added', {
                'product_id': str(instance.product_id),
                'quantity': instance.quantity,
            })
            logger.debug(f"Item added to cart {cart.id}: product {instance.product_id}")
        else:
            update_fields = kwargs.get('update_fields') or []
            if 'quantity' in update_fields:
                _log_cart_event(cart, 'item_updated', {
                    'product_id': str(instance.product_id),
                    'quantity': instance.quantity,
                })
        
        # Recalculate cart totals
        cart.recalculate_totals()
        
    except Exception as e:
        logger.warning(f"Error processing cart item signal: {e}")


@receiver(post_delete, sender='cart.CartItem')
def on_cart_item_deleted(sender, instance, **kwargs):
    """Handle cart item removal."""
    try:
        cart = instance.cart
        _log_cart_event(cart, 'item_removed', {
            'product_id': str(instance.product_id),
        })
        
        # Recalculate cart totals
        cart.recalculate_totals()
        
        logger.debug(f"Item removed from cart {cart.id}: product {instance.product_id}")
        
    except Exception as e:
        logger.warning(f"Error processing cart item deletion: {e}")


@receiver(pre_save, sender='cart.Cart')
def check_cart_abandonment(sender, instance, **kwargs):
    """Check if cart should be marked as abandoned."""
    try:
        if not instance.pk:
            return
            
        # Get original cart
        original = sender.objects.filter(pk=instance.pk).first()
        if not original:
            return
        
        # If cart was active and now being updated after long inactivity
        abandonment_threshold = timezone.now() - timedelta(hours=24)
        if (original.status == 'active' and 
            original.last_activity_at and 
            original.last_activity_at < abandonment_threshold):
            
            # Mark as abandoned if still has items
            if original.items.exists():
                logger.info(f"Cart {instance.id} marked as abandoned after inactivity")
                
    except Exception as e:
        logger.warning(f"Error checking cart abandonment: {e}")


def _log_cart_event(cart, event_type, data=None):
    """Log cart events for analytics."""
    try:
        from .models import CartEvent
        CartEvent.objects.create(
            cart=cart,
            event_type=event_type,
            data=data or {}
        )
    except Exception as e:
        logger.debug(f"Could not log cart event: {e}")
