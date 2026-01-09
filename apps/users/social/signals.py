"""Users Social - Signal Handlers.

Social account linking and OAuth events.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger('apps.social.signals')


@receiver(post_save, sender='social.SocialConnection')
def on_social_connection_linked(sender, instance, created, **kwargs):
    """Handle social account linking."""
    if not created:
        return
    
    try:
        provider_name = instance.get_provider_display() if hasattr(instance, 'get_provider_display') else instance.provider
        
        # Send notification to user
        _send_social_notification(
            instance.user,
            'social_linked',
            f'Social Account Linked: {provider_name}'
        )
        
        logger.info(f"Social account {instance.provider} linked for user {instance.user.email}")
        
    except Exception as e:
        logger.warning(f"Error processing social account link: {e}")


@receiver(post_delete, sender='social.SocialConnection')
def on_social_connection_unlinked(sender, instance, **kwargs):
    """Handle social account unlinking."""
    try:
        provider_name = instance.get_provider_display() if hasattr(instance, 'get_provider_display') else instance.provider
        
        # Send notification to user
        _send_social_notification(
            instance.user,
            'social_unlinked',
            f'Social Account Unlinked: {provider_name}'
        )
        
        logger.info(f"Social account {instance.provider} unlinked for user {instance.user.email}")
        
    except Exception as e:
        logger.warning(f"Error processing social account unlink: {e}")


@receiver(post_save, sender='social.SocialLoginLog')
def on_social_login_log_created(sender, instance, created, **kwargs):
    """Log social login attempts."""
    if not created:
        return
    
    try:
        if instance.status == 'failed' or instance.status == 'error':
            logger.warning(f"Social login failed: {instance.provider} - {instance.error_message}")
        else:
            logger.debug(f"Social login success: {instance.provider}")
            
    except Exception as e:
        logger.warning(f"Error processing social login log: {e}")


def _send_social_notification(user, notification_type, message):
    """Send social-related notification to user."""
    if not user:
        return
    
    try:
        from apps.users.notifications.services import NotificationService
        
        NotificationService.create(
            user=user,
            notification_type=notification_type,
            title='Account Update',
            message=message,
            data={'is_social_update': True}
        )
    except Exception as e:
        logger.debug(f"Could not send social notification: {e}")
