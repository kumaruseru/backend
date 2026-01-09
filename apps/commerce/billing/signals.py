"""Commerce Billing - Signal Handlers.

Payment transaction events and notifications.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger('apps.billing.signals')


@receiver(post_save, sender='billing.PaymentTransaction')
def on_payment_transaction_saved(sender, instance, created, **kwargs):
    """Handle payment transaction status changes."""
    try:
        if instance.status == 'completed':
            # Update order payment status
            if instance.order:
                instance.order.payment_status = 'paid'
                instance.order.paid_at = timezone.now()
                instance.order.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
                logger.info(f"Order {instance.order.order_number} marked as paid")
            
            # Trigger notification to customer
            if instance.user:
                _send_payment_notification(instance, 'payment_success')
        
        elif instance.status == 'failed':
            if instance.order:
                instance.order.payment_status = 'failed'
                instance.order.save(update_fields=['payment_status', 'updated_at'])
            
            if instance.user:
                _send_payment_notification(instance, 'payment_failed')
                
    except Exception as e:
        logger.warning(f"Error processing payment transaction signal: {e}")


@receiver(post_save, sender='billing.PaymentRefund')
def on_refund_saved(sender, instance, created, **kwargs):
    """Handle refund status changes."""
    try:
        if instance.status == 'completed':
            # Update order payment status
            if instance.transaction and instance.transaction.order:
                order = instance.transaction.order
                # Check if fully refunded
                total_refunded = order.refunds.filter(status='completed').aggregate(
                    total=models.Sum('amount')
                )['total'] or 0
                
                if total_refunded >= order.total_amount:
                    order.payment_status = 'refunded'
                else:
                    order.payment_status = 'partial_refund'
                order.save(update_fields=['payment_status', 'updated_at'])
            
            # Notify customer
            if instance.transaction and instance.transaction.user:
                _send_refund_notification(instance)
                
    except Exception as e:
        logger.warning(f"Error processing refund signal: {e}")


def _send_payment_notification(transaction, notification_type):
    """Send payment notification to user."""
    try:
        from apps.users.notifications.services import NotificationService
        NotificationService.create(
            user=transaction.user,
            notification_type=notification_type,
            title='Payment Successful' if notification_type == 'payment_success' else 'Payment Failed',
            message=f"Your payment of {transaction.amount:,.0f}₫ {'was successful' if notification_type == 'payment_success' else 'has failed'}.",
            data={
                'transaction_id': str(transaction.id),
                'order_number': transaction.order.order_number if transaction.order else None,
                'amount': float(transaction.amount),
            }
        )
    except Exception as e:
        logger.debug(f"Could not send payment notification: {e}")


def _send_refund_notification(refund):
    """Send refund notification to user."""
    try:
        from apps.users.notifications.services import NotificationService
        NotificationService.create(
            user=refund.transaction.user,
            notification_type='refund_completed',
            title='Refund Processed',
            message=f"Your refund of {refund.amount:,.0f}₫ has been processed.",
            data={
                'refund_id': str(refund.id),
                'amount': float(refund.amount),
            }
        )
    except Exception as e:
        logger.debug(f"Could not send refund notification: {e}")
