"""Store Inventory - Signal Handlers.

Stock level monitoring and low stock alerts.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger('apps.inventory.signals')


@receiver(post_save, sender='inventory.StockItem')
def on_stock_item_saved(sender, instance, created, **kwargs):
    """Handle stock level changes."""
    try:
        # Invalidate product stock cache
        cache.delete(f'product:{instance.product_id}:stock')
        
        if created:
            logger.debug(f"Stock item created for product {instance.product_id}")
            return
        
        update_fields = kwargs.get('update_fields') or []
        
        # Check if quantity changed
        if 'quantity' in update_fields or 'reserved_quantity' in update_fields:
            # Check for low stock
            if instance.is_low_stock:
                _create_low_stock_alert(instance)
            elif instance.is_out_of_stock:
                _create_out_of_stock_alert(instance)
                
    except Exception as e:
        logger.warning(f"Error processing stock item signal: {e}")


@receiver(post_save, sender='inventory.StockAlert')
def on_stock_alert_created(sender, instance, created, **kwargs):
    """Notify admins about new stock alerts."""
    if not created:
        return
    
    try:
        _notify_admin_stock_alert(instance)
    except Exception as e:
        logger.warning(f"Error notifying stock alert: {e}")


@receiver(post_save, sender='inventory.StockMovement')
def on_stock_movement_saved(sender, instance, created, **kwargs):
    """Log significant stock movements."""
    if not created:
        return
    
    try:
        # Invalidate movement cache
        cache.delete(f'stock:{instance.stock_id}:movements')
        
        # Log large movements
        if abs(instance.quantity_change) >= 50:
            logger.info(
                f"Large stock movement: {instance.stock.product.name} "
                f"({instance.quantity_change:+d}) - {instance.get_reason_display()}"
            )
            
    except Exception as e:
        logger.warning(f"Error processing stock movement signal: {e}")


def _create_low_stock_alert(stock_item):
    """Create low stock alert if not already exists."""
    try:
        from .models import StockAlert
        
        exists = StockAlert.objects.filter(
            stock=stock_item,
            alert_type='low_stock',
            is_resolved=False
        ).exists()
        
        if not exists:
            StockAlert.objects.create(
                stock=stock_item,
                alert_type='low_stock',
                threshold=stock_item.low_stock_threshold,
                current_quantity=stock_item.available_quantity
            )
            logger.info(f"Low stock alert created for {stock_item.product.name}")
            
    except Exception as e:
        logger.debug(f"Could not create low stock alert: {e}")


def _create_out_of_stock_alert(stock_item):
    """Create out of stock alert if not already exists."""
    try:
        from .models import StockAlert
        
        exists = StockAlert.objects.filter(
            stock=stock_item,
            alert_type='out_of_stock',
            is_resolved=False
        ).exists()
        
        if not exists:
            StockAlert.objects.create(
                stock=stock_item,
                alert_type='out_of_stock',
                threshold=0,
                current_quantity=0
            )
            logger.warning(f"Out of stock alert created for {stock_item.product.name}")
            
    except Exception as e:
        logger.debug(f"Could not create out of stock alert: {e}")


def _notify_admin_stock_alert(alert):
    """Notify admins about stock alerts."""
    try:
        from apps.users.identity.models import User
        from apps.users.notifications.services import NotificationService
        
        title = 'Out of Stock Alert' if alert.alert_type == 'out_of_stock' else 'Low Stock Alert'
        message = f"{alert.stock.product.name} - {alert.current_quantity} units remaining"
        
        admins = User.objects.filter(is_staff=True, is_active=True)[:3]
        for admin in admins:
            NotificationService.create(
                user=admin,
                notification_type='stock_alert',
                title=title,
                message=message,
                data={
                    'alert_id': alert.id,
                    'product_id': str(alert.stock.product_id),
                    'alert_type': alert.alert_type,
                    'quantity': alert.current_quantity,
                }
            )
    except Exception as e:
        logger.debug(f"Could not notify admins about stock alert: {e}")
