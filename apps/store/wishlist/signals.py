"""Store Wishlist - Signal Handlers.

Wishlist notifications and analytics.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger('apps.wishlist.signals')


@receiver(post_save, sender='wishlist.WishlistItem')
def on_wishlist_item_added(sender, instance, created, **kwargs):
    """Track wishlist additions for product analytics."""
    if not created:
        return
    
    try:
        # Update product wishlist count
        _update_product_wishlist_count(instance.product_id, 1)
        
        # Invalidate user wishlist cache
        if instance.wishlist.user_id:
            cache.delete(f'user:{instance.wishlist.user_id}:wishlist')
        
        logger.debug(f"Product {instance.product_id} added to wishlist")
        
    except Exception as e:
        logger.warning(f"Error processing wishlist item addition: {e}")


@receiver(post_delete, sender='wishlist.WishlistItem')
def on_wishlist_item_removed(sender, instance, **kwargs):
    """Track wishlist removals."""
    try:
        # Update product wishlist count
        _update_product_wishlist_count(instance.product_id, -1)
        
        # Invalidate user wishlist cache
        if instance.wishlist.user_id:
            cache.delete(f'user:{instance.wishlist.user_id}:wishlist')
        
        logger.debug(f"Product {instance.product_id} removed from wishlist")
        
    except Exception as e:
        logger.warning(f"Error processing wishlist item removal: {e}")


@receiver(post_save, sender='wishlist.Wishlist')
def on_wishlist_created(sender, instance, created, **kwargs):
    """Handle wishlist creation."""
    if not created:
        return
    
    try:
        logger.debug(f"Wishlist created for user {instance.user_id}")
    except Exception as e:
        logger.warning(f"Error processing wishlist creation: {e}")


def _update_product_wishlist_count(product_id, delta):
    """Update product wishlist count for analytics."""
    try:
        from apps.commerce.analytics.models import ProductAnalytics
        from django.db.models import F
        
        ProductAnalytics.objects.filter(product_id=product_id).update(
            total_wishlist_adds=F('total_wishlist_adds') + delta
        )
        
        # Invalidate product cache
        cache.delete(f'product:{product_id}:analytics')
        
    except Exception as e:
        logger.debug(f"Could not update product wishlist count: {e}")


def notify_wishlist_price_drop(product):
    """Notify users when a wishlisted product price drops."""
    try:
        from .models import WishlistItem
        from apps.users.notifications.services import NotificationService
        
        # Find all users who have this product in their wishlist
        wishlist_items = WishlistItem.objects.filter(
            product_id=product.id
        ).select_related('wishlist__user')
        
        for item in wishlist_items:
            user = item.wishlist.user
            if user:
                NotificationService.create(
                    user=user,
                    notification_type='price_drop',
                    title='Price Drop Alert!',
                    message=f"{product.name} is now on sale!",
                    data={
                        'product_id': str(product.id),
                        'product_name': product.name,
                        'new_price': float(product.current_price),
                    }
                )
                
        logger.info(f"Notified {wishlist_items.count()} users about price drop for {product.name}")
        
    except Exception as e:
        logger.warning(f"Error notifying wishlist price drop: {e}")
