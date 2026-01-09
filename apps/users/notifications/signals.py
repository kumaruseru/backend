import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Notification

logger = logging.getLogger('apps.notifications')


@receiver(post_save, sender=Notification)
def on_notification_created(sender, instance, created, **kwargs):
    if created:
        cache.delete(f'user:{instance.user_id}:notifications:unread_count')
        logger.debug(f"Notification created: {instance.notification_type} for {instance.user.email}")


@receiver(post_save, sender=Notification)
def on_notification_read(sender, instance, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields and 'is_read' in update_fields:
        cache.delete(f'user:{instance.user_id}:notifications:unread_count')
