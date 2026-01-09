"""Commerce Analytics - Signal Handlers.

Event-driven analytics updates triggered by commerce events.
Provides real-time metric updates for key business transactions.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger('apps.analytics.signals')


# Import models lazily to avoid circular imports
def get_order_model():
    from apps.commerce.orders.models import Order
    return Order


def get_return_model():
    from apps.commerce.returns.models import ReturnRequest
    return ReturnRequest


def get_shipment_model():
    from apps.commerce.shipping.models import Shipment
    return Shipment


def get_cart_model():
    from apps.commerce.cart.models import Cart
    return Cart


def get_daily_metric_model():
    from .models import DailyMetric
    return DailyMetric


def get_product_analytics_model():
    from .models import ProductAnalytics
    return ProductAnalytics


def get_customer_segment_model():
    from .models import CustomerSegment
    return CustomerSegment


@receiver(post_save, sender='orders.Order')
def on_order_saved(sender, instance, created, **kwargs):
    """Update analytics when an order is created or status changes."""
    try:
        DailyMetric = get_daily_metric_model()
        today = timezone.now().date()
        
        if created:
            # Increment order count for today
            metric, _ = DailyMetric.objects.get_or_create(date=today)
            metric.total_orders += 1
            metric.total_revenue += instance.total
            metric.save(update_fields=['total_orders', 'total_revenue', 'updated_at'])
            
            logger.debug(f"Order {instance.order_number} created - metrics updated")
            
            # Update customer segment asynchronously
            if instance.user_id:
                from .tasks import update_customer_segments
                # We could trigger individual update but batch is more efficient
                # update_customer_segments.delay()
        
    except Exception as e:
        logger.warning(f"Error updating analytics on order save: {e}")


@receiver(post_save, sender='orders.OrderItem')
def on_order_item_saved(sender, instance, created, **kwargs):
    """Update product analytics when order items are saved."""
    try:
        if created and instance.product_id:
            ProductAnalytics = get_product_analytics_model()
            
            analytics, _ = ProductAnalytics.objects.get_or_create(
                product_id=instance.product_id
            )
            
            analytics.total_purchases += 1
            analytics.total_quantity_sold += instance.quantity
            analytics.total_revenue += instance.subtotal
            analytics.save(update_fields=[
                'total_purchases', 'total_quantity_sold', 'total_revenue', 'updated_at'
            ])
            
            logger.debug(f"Product {instance.product_id} analytics updated")
            
    except Exception as e:
        logger.warning(f"Error updating product analytics on order item: {e}")


@receiver(post_save, sender='returns.ReturnRequest')
def on_return_request_saved(sender, instance, created, **kwargs):
    """Update analytics when return requests are processed."""
    try:
        if created:
            DailyMetric = get_daily_metric_model()
            today = timezone.now().date()
            
            metric, _ = DailyMetric.objects.get_or_create(date=today)
            metric.return_requests += 1
            metric.save(update_fields=['return_requests', 'updated_at'])
            
            logger.debug(f"Return request {instance.request_number} - metrics updated")
        
        # When return is completed, update refund amount
        if instance.status == 'completed' and instance.approved_refund:
            DailyMetric = get_daily_metric_model()
            today = timezone.now().date()
            
            metric, _ = DailyMetric.objects.get_or_create(date=today)
            metric.total_refund_amount += instance.approved_refund
            metric.save(update_fields=['total_refund_amount', 'updated_at'])
            
    except Exception as e:
        logger.warning(f"Error updating analytics on return request: {e}")


@receiver(post_save, sender='cart.Cart')
def on_cart_saved(sender, instance, created, **kwargs):
    """Track cart creation for conversion funnel."""
    try:
        if created:
            DailyMetric = get_daily_metric_model()
            today = timezone.now().date()
            
            metric, _ = DailyMetric.objects.get_or_create(date=today)
            metric.carts_created += 1
            metric.save(update_fields=['carts_created', 'updated_at'])
            
            logger.debug(f"Cart created - metrics updated")
            
    except Exception as e:
        logger.warning(f"Error updating analytics on cart creation: {e}")


@receiver(post_save, sender='cart.CartItem')
def on_cart_item_saved(sender, instance, created, **kwargs):
    """Track add-to-cart events for product analytics."""
    try:
        if created and instance.product_id:
            ProductAnalytics = get_product_analytics_model()
            
            analytics, _ = ProductAnalytics.objects.get_or_create(
                product_id=instance.product_id
            )
            
            analytics.total_cart_adds += 1
            analytics.cart_adds_30d += 1
            analytics.calculate_rates()
            analytics.save()
            
            logger.debug(f"Product {instance.product_id} cart add tracked")
            
    except Exception as e:
        logger.warning(f"Error updating product analytics on cart item: {e}")


@receiver(post_save, sender='shipping.Shipment')
def on_shipment_saved(sender, instance, **kwargs):
    """Track shipment status for order completion analytics."""
    try:
        if instance.status == 'delivered':
            DailyMetric = get_daily_metric_model()
            today = timezone.now().date()
            
            metric, _ = DailyMetric.objects.get_or_create(date=today)
            metric.completed_orders += 1
            metric.save(update_fields=['completed_orders', 'updated_at'])
            
            logger.debug(f"Shipment delivered - completed orders incremented")
            
    except Exception as e:
        logger.warning(f"Error updating analytics on shipment: {e}")
