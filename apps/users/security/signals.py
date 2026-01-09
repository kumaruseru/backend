"""Users Security - Signal Handlers.

Security events, 2FA, and suspicious activity detection.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger('apps.security.signals')


@receiver(post_save, sender='security.TwoFactorConfig')
def on_2fa_config_changed(sender, instance, created, **kwargs):
    """Handle 2FA configuration changes."""
    try:
        if created and instance.is_enabled:
            _send_security_notification(instance.user, '2fa_enabled', 'Two-Factor Authentication Enabled')
            logger.info(f"2FA enabled for user {instance.user.email}")
        elif not created:
            update_fields = kwargs.get('update_fields') or []
            if 'is_enabled' in update_fields:
                if instance.is_enabled:
                    _send_security_notification(instance.user, '2fa_enabled', 'Two-Factor Authentication Enabled')
                else:
                    _send_security_notification(instance.user, '2fa_disabled', 'Two-Factor Authentication Disabled')
                    logger.info(f"2FA disabled for user {instance.user.email}")
                    
    except Exception as e:
        logger.warning(f"Error processing 2FA signal: {e}")


@receiver(post_save, sender='security.APIKey')
def on_api_key_created(sender, instance, created, **kwargs):
    """Handle API key creation."""
    if not created:
        return
    
    try:
        if instance.user:
            _send_security_notification(
                instance.user, 
                'api_key_created', 
                f"New API Key Created: {instance.name}"
            )
        logger.info(f"API key '{instance.name}' created for user {instance.user.email if instance.user else 'system'}")
        
    except Exception as e:
        logger.warning(f"Error processing API key signal: {e}")


@receiver(post_save, sender='security.TrustedDevice')
def on_trusted_device_added(sender, instance, created, **kwargs):
    """Handle trusted device changes."""
    if not created:
        return
    
    try:
        if instance.user:
            _send_security_notification(
                instance.user,
                'new_device',
                f"New Device Trusted: {instance.device_name}"
            )
            
        # Invalidate trusted devices cache
        cache.delete(f'user:{instance.user_id}:trusted_devices')
        
        logger.debug(f"New trusted device for user {instance.user.email}")
        
    except Exception as e:
        logger.warning(f"Error processing trusted device signal: {e}")


@receiver(post_save, sender='security.IPBlacklist')
def on_ip_blacklisted(sender, instance, created, **kwargs):
    """Handle IP blacklist changes."""
    try:
        # Invalidate blacklist cache
        cache.delete('security:ip_blacklist')
        
        if created:
            logger.warning(f"IP {instance.ip_address} added to blacklist: {instance.reason}")
            
    except Exception as e:
        logger.warning(f"Error processing IP blacklist signal: {e}")


def _send_security_notification(user, notification_type, title):
    """Send security-related notification to user."""
    try:
        from apps.users.notifications.services import NotificationService
        
        NotificationService.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=f"Security alert: {title}. If this wasn't you, please contact support immediately.",
            data={
                'is_security_alert': True,
                'timestamp': timezone.now().isoformat(),
            }
        )
    except Exception as e:
        logger.debug(f"Could not send security notification: {e}")
