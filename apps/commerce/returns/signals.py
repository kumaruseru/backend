"""Commerce Returns - Signal Handlers.

Return request lifecycle events and inventory processing.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger('apps.returns.signals')


@receiver(pre_save, sender='returns.ReturnRequest')
def on_return_status_changing(sender, instance, **kwargs):
    """Track return request status changes."""
    if not instance.pk:
        return
    
    try:
        original = sender.objects.filter(pk=instance.pk).only('status').first()
        if original and original.status != instance.status:
            instance._status_changed = True
            instance._old_status = original.status
            instance._new_status = instance.status
    except Exception as e:
        logger.warning(f"Error tracking return status change: {e}")


@receiver(post_save, sender='returns.ReturnRequest')
def on_return_saved(sender, instance, created, **kwargs):
    """Handle return request creation and status changes."""
    try:
        if created:
            # Notify customer
            _send_return_notification(instance, 'return_submitted')
            # Notify admin
            _notify_admin_new_return(instance)
            logger.info(f"Return request {instance.request_number} created")
            return
        
        if not getattr(instance, '_status_changed', False):
            return
        
        new_status = instance._new_status
        
        if new_status == 'approved':
            _send_return_notification(instance, 'return_approved')
            
        elif new_status == 'rejected':
            _send_return_notification(instance, 'return_rejected')
            
        elif new_status == 'received':
            _send_return_notification(instance, 'return_received')
            
        elif new_status == 'completed':
            # Process inventory return
            _process_inventory_return(instance)
            _send_return_notification(instance, 'return_completed')
            
        # Cleanup
        if hasattr(instance, '_status_changed'):
            del instance._status_changed
            del instance._old_status
            del instance._new_status
            
    except Exception as e:
        logger.warning(f"Error processing return signal: {e}")


def _process_inventory_return(return_request):
    """Add returned items back to inventory."""
    try:
        from apps.store.inventory.services import InventoryService
        
        for item in return_request.items.filter(accepted_quantity__gt=0):
            if item.order_item and item.order_item.product_id:
                InventoryService.process_return(
                    product_id=item.order_item.product_id,
                    quantity=item.accepted_quantity,
                    reference=return_request.request_number
                )
                
    except Exception as e:
        logger.warning(f"Error processing inventory return: {e}")


def _send_return_notification(return_request, notification_type):
    """Send return-related notification to customer."""
    if not return_request.user:
        return
    
    try:
        from apps.users.notifications.services import NotificationService
        
        titles = {
            'return_submitted': 'Return Request Submitted',
            'return_approved': 'Return Request Approved',
            'return_rejected': 'Return Request Rejected',
            'return_received': 'Return Items Received',
            'return_completed': 'Return Completed',
        }
        
        NotificationService.create(
            user=return_request.user,
            notification_type=notification_type,
            title=titles.get(notification_type, 'Return Update'),
            message=f"Return request #{return_request.request_number} - {titles.get(notification_type, 'Status updated')}",
            data={
                'return_id': str(return_request.id),
                'request_number': return_request.request_number,
                'status': return_request.status,
            }
        )
    except Exception as e:
        logger.debug(f"Could not send return notification: {e}")


def _notify_admin_new_return(return_request):
    """Notify admins about new return request."""
    try:
        from apps.users.identity.models import User
        from apps.users.notifications.services import NotificationService
        
        admins = User.objects.filter(is_staff=True, is_active=True)[:5]
        for admin in admins:
            NotificationService.create(
                user=admin,
                notification_type='admin_new_return',
                title='New Return Request',
                message=f"Return request #{return_request.request_number} needs review.",
                data={
                    'return_id': str(return_request.id),
                    'order_number': return_request.order.order_number if return_request.order else None,
                }
            )
    except Exception as e:
        logger.debug(f"Could not notify admins: {e}")
