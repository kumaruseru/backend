"""
Users Notifications - Django Signals.

Signal handlers for notification events.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

from .models import Notification

logger = logging.getLogger('apps.notifications')


@receiver(post_save, sender=Notification)
def on_notification_created(sender, instance, created, **kwargs):
    """Handle new notification creation."""
    if created:
        # Invalidate unread count cache
        cache.delete(f'user:{instance.user_id}:notifications:unread_count')
        
        logger.debug(f"Notification created: {instance.notification_type} for {instance.user.email}")


@receiver(post_save, sender=Notification)
def on_notification_read(sender, instance, **kwargs):
    """Handle notification read status change."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'is_read' in update_fields:
        # Invalidate unread count cache
        cache.delete(f'user:{instance.user_id}:notifications:unread_count')
