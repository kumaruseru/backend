"""Users Identity - Signal Handlers.

User lifecycle events, profile updates, and security tracking.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger('apps.identity.signals')


@receiver(post_save, sender='identity.User')
def on_user_saved(sender, instance, created, **kwargs):
    """Handle user creation and updates."""
    try:
        if created:
            # Create related models
            _create_user_preferences(instance)
            
            # Send welcome notification
            _send_welcome_notification(instance)
            
            logger.info(f"New user registered: {instance.email}")
            return
        
        # Invalidate user cache on updates
        cache.delete(f'user:{instance.id}:profile')
        
    except Exception as e:
        logger.warning(f"Error processing user signal: {e}")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Track successful login events."""
    try:
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Log login event
        _create_login_history(user, request, success=True)
        
        logger.debug(f"User {user.email} logged in")
        
    except Exception as e:
        logger.warning(f"Error processing login signal: {e}")


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Handle logout events."""
    try:
        if user:
            # Invalidate user session cache
            cache.delete(f'user:{user.id}:session')
            logger.debug(f"User {user.email} logged out")
            
    except Exception as e:
        logger.warning(f"Error processing logout signal: {e}")


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    """Track failed login attempts."""
    try:
        email = credentials.get('email', credentials.get('username', 'unknown'))
        
        # Log failed attempt
        _create_login_history_failed(email, request)
        
        logger.warning(f"Failed login attempt for: {email}")
        
    except Exception as e:
        logger.warning(f"Error processing login failure signal: {e}")


@receiver(post_save, sender='identity.UserAddress')
def on_address_saved(sender, instance, created, **kwargs):
    """Handle address changes."""
    try:
        # Invalidate address cache
        cache.delete(f'user:{instance.user_id}:addresses')
        
        # If set as default, unset other defaults
        if instance.is_default:
            sender.objects.filter(
                user_id=instance.user_id,
                is_default=True
            ).exclude(pk=instance.pk).update(is_default=False)
            
    except Exception as e:
        logger.warning(f"Error processing address signal: {e}")


def _create_user_preferences(user):
    """Create default user preferences."""
    try:
        from .models import UserPreferences
        UserPreferences.objects.get_or_create(user=user)
    except Exception as e:
        logger.debug(f"Could not create user preferences: {e}")


def _send_welcome_notification(user):
    """Send welcome notification to new user."""
    try:
        from apps.users.notifications.services import NotificationService
        NotificationService.create(
            user=user,
            notification_type='welcome',
            title='Welcome to Owls!',
            message='Thank you for joining us. Start exploring our products!',
            data={'is_welcome': True}
        )
    except Exception as e:
        logger.debug(f"Could not send welcome notification: {e}")


def _create_login_history(user, request, success=True):
    """Create login history record."""
    try:
        from .models import LoginHistory
        
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        
        LoginHistory.objects.create(
            user=user,
            ip_address=ip[:45] if ip else '',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            success=success
        )
    except Exception as e:
        logger.debug(f"Could not create login history: {e}")


def _create_login_history_failed(email, request):
    """Create failed login record."""
    try:
        from .models import User, LoginHistory
        
        user = User.objects.filter(email=email).first()
        if not user:
            return
        
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        
        LoginHistory.objects.create(
            user=user,
            ip_address=ip[:45] if ip else '',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            success=False
        )
    except Exception as e:
        logger.debug(f"Could not create failed login history: {e}")
