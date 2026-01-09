"""Store Marketing - Signal Handlers.

Coupon usage tracking and campaign analytics.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger('apps.marketing.signals')


@receiver(post_save, sender='marketing.CouponUsage')
def on_coupon_used(sender, instance, created, **kwargs):
    """Track coupon usage and update coupon stats."""
    if not created:
        return
    
    try:
        coupon = instance.coupon
        
        # Increment used count
        from django.db.models import F
        from .models import Coupon
        Coupon.objects.filter(pk=coupon.pk).update(used_count=F('used_count') + 1)
        
        # Invalidate coupon cache
        cache.delete(f'coupon:{coupon.code}')
        
        logger.info(f"Coupon {coupon.code} used by {instance.user.email}")
        
    except Exception as e:
        logger.warning(f"Error processing coupon usage signal: {e}")


@receiver(post_save, sender='marketing.FlashSale')
def on_flash_sale_saved(sender, instance, created, **kwargs):
    """Handle flash sale status changes."""
    try:
        # Invalidate flash sale cache
        cache.delete('flash_sales:active')
        cache.delete(f'flash_sale:{instance.id}')
        
        if created:
            logger.info(f"Flash sale '{instance.name}' created")
        
    except Exception as e:
        logger.warning(f"Error processing flash sale signal: {e}")


@receiver(post_save, sender='marketing.Banner')
def on_banner_saved(sender, instance, created, **kwargs):
    """Invalidate banner cache on changes."""
    try:
        cache.delete(f'banners:{instance.position}')
        cache.delete('banners:all')
        
    except Exception as e:
        logger.warning(f"Error processing banner signal: {e}")


@receiver(post_save, sender='marketing.Campaign')
def on_campaign_saved(sender, instance, created, **kwargs):
    """Track campaign status changes."""
    try:
        if created:
            logger.info(f"Campaign '{instance.name}' created")
            return
        
        update_fields = kwargs.get('update_fields') or []
        
        if 'status' in update_fields:
            if instance.status == 'active':
                logger.info(f"Campaign '{instance.name}' activated")
            elif instance.status == 'completed':
                logger.info(f"Campaign '{instance.name}' completed")
                
    except Exception as e:
        logger.warning(f"Error processing campaign signal: {e}")
