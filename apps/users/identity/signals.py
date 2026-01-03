"""
Users Identity - Production-Ready Django Signals.

Comprehensive signal handlers for:
- User lifecycle management
- Session tracking and security
- Login monitoring and alerts
- Preference sync and cleanup
"""
import logging
from datetime import timedelta
from functools import wraps

from django.db import transaction
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .models import User, UserPreferences, UserSession, LoginHistory, AccountDeletionRequest

logger = logging.getLogger('apps.identity')


# ==================== Signal Utilities ====================

def signal_handler(func):
    """
    Decorator for safe signal handling with error logging.
    Prevents signal errors from breaking the main operation.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Signal handler error in {func.__name__}: {e}")
            # Don't re-raise - signals shouldn't break main operations
    return wrapper


def on_transaction_commit(func):
    """
    Decorator to run signal handler after transaction commits.
    Useful for signals that trigger async tasks or external calls.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        transaction.on_commit(lambda: func(*args, **kwargs))
    return wrapper


# ==================== User Signals ====================

@receiver(pre_save, sender=User)
@signal_handler
def normalize_user_data(sender, instance, **kwargs):
    """
    Normalize user data before saving.
    - Email to lowercase
    - Phone formatting
    - Name trimming
    """
    if instance.email:
        instance.email = instance.email.lower().strip()
    
    if instance.first_name:
        instance.first_name = instance.first_name.strip()
    
    if instance.last_name:
        instance.last_name = instance.last_name.strip()
    
    # Format phone number
    if instance.phone:
        phone = instance.phone.strip()
        # Convert 0xxx to +84xxx if Vietnamese
        if phone.startswith('0') and len(phone) == 10:
            phone = '+84' + phone[1:]
        instance.phone = phone


@receiver(post_save, sender=User)
@signal_handler
def on_user_created(sender, instance, created, **kwargs):
    """Handle new user creation."""
    if not created:
        return
    
    # Create default preferences
    UserPreferences.objects.get_or_create(user=instance)
    
    logger.info(f"New user created: {instance.email} (ID: {instance.id})")
    
    # Invalidate any cached user counts
    cache.delete('users:total_count')
    cache.delete('users:active_count')


@receiver(post_save, sender=User)
@signal_handler
def on_email_verified(sender, instance, **kwargs):
    """Handle email verification."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'is_email_verified' in update_fields:
        if instance.is_email_verified:
            logger.info(f"Email verified: {instance.email}")
            
            # Queue welcome email (async)
            _queue_welcome_email(instance)


@receiver(post_save, sender=User)
@signal_handler  
def on_user_deactivated(sender, instance, **kwargs):
    """Handle user deactivation."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'is_active' in update_fields:
        if not instance.is_active:
            logger.warning(f"User deactivated: {instance.email}")
            
            # Terminate all sessions
            UserSession.objects.filter(
                user=instance,
                is_active=True
            ).update(is_active=False)


@receiver(post_save, sender=User)
@signal_handler
def on_password_changed(sender, instance, **kwargs):
    """Handle password change."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'password' in update_fields:
        logger.info(f"Password changed for: {instance.email}")
        
        # Terminate all other sessions for security
        UserSession.objects.filter(
            user=instance,
            is_active=True
        ).update(is_active=False)
        
        # Queue security notification
        _queue_password_change_notification(instance)


@receiver(post_delete, sender=User)
@signal_handler
def on_user_deleted(sender, instance, **kwargs):
    """Handle user deletion cleanup."""
    logger.info(f"User deleted: {instance.email} (ID: {instance.id})")
    
    # Clear user-related caches
    cache.delete(f'user:{instance.id}:profile')
    cache.delete(f'user:{instance.id}:preferences')
    cache.delete('users:total_count')


# ==================== Session Signals ====================

@receiver(post_save, sender=UserSession)
@signal_handler
def on_session_created(sender, instance, created, **kwargs):
    """Handle new session creation."""
    if not created:
        return
    
    logger.info(
        f"New session: user={instance.user.email}, "
        f"device={instance.device_type}, browser={instance.browser}, "
        f"ip={instance.ip_address}"
    )
    
    # Check if new device
    _check_new_device_login(instance)
    
    # Cleanup old expired sessions
    _cleanup_expired_sessions(instance.user)


@receiver(post_save, sender=UserSession)
@signal_handler
def on_session_terminated(sender, instance, **kwargs):
    """Handle session termination."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'is_active' in update_fields:
        if not instance.is_active:
            logger.info(f"Session terminated: {instance.session_key[:8]}...")


# ==================== Login History Signals ====================

@receiver(post_save, sender=LoginHistory)
@signal_handler
def on_login_recorded(sender, instance, created, **kwargs):
    """Handle login record creation."""
    if not created:
        return
    
    if instance.status == 'success':
        _handle_successful_login(instance)
    elif instance.status == 'failed':
        _handle_failed_login(instance)
    elif instance.status == 'blocked':
        _handle_blocked_login(instance)


# ==================== Account Deletion Signals ====================

@receiver(post_save, sender=AccountDeletionRequest)
@signal_handler
def on_deletion_request_created(sender, instance, created, **kwargs):
    """Handle deletion request creation."""
    if created:
        logger.warning(
            f"Account deletion requested: {instance.user.email}, "
            f"scheduled for: {instance.scheduled_at}"
        )
        
        # Queue confirmation email
        _queue_deletion_confirmation_email(instance)


@receiver(post_save, sender=AccountDeletionRequest)
@signal_handler
def on_deletion_request_status_changed(sender, instance, **kwargs):
    """Handle deletion request status changes."""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and 'status' in update_fields:
        if instance.status == 'cancelled':
            logger.info(f"Deletion cancelled: {instance.user.email}")
        elif instance.status == 'approved':
            logger.warning(f"Deletion approved: {instance.user.email}")
        elif instance.status == 'completed':
            logger.info(f"Account deleted: {instance.user.email}")


# ==================== Preferences Signals ====================

@receiver(post_save, sender=UserPreferences)
@signal_handler
def on_preferences_updated(sender, instance, **kwargs):
    """Handle preference updates."""
    # Invalidate preference cache
    cache.delete(f'user:{instance.user_id}:preferences')


# ==================== Helper Functions ====================

def _check_new_device_login(session: UserSession):
    """Check if login is from a new device and notify user."""
    user = session.user
    
    # Check preferences
    try:
        if not user.preferences.login_notification:
            return
    except UserPreferences.DoesNotExist:
        return
    
    # Check for existing sessions with same device fingerprint
    existing = UserSession.objects.filter(
        user=user,
        device_type=session.device_type,
        browser=session.browser,
        os=session.os
    ).exclude(id=session.id).exists()
    
    if not existing:
        logger.info(f"New device detected for {user.email}: {session.device_name}")
        _queue_new_device_notification(session)


def _cleanup_expired_sessions(user: User):
    """Cleanup expired sessions for a user."""
    expired_count = UserSession.objects.filter(
        user=user,
        expires_at__lt=timezone.now()
    ).update(is_active=False)
    
    if expired_count:
        logger.debug(f"Cleaned up {expired_count} expired sessions for {user.email}")


def _handle_successful_login(login: LoginHistory):
    """Handle successful login event."""
    # Check for location change
    if login.user:
        last_login = LoginHistory.objects.filter(
            user=login.user,
            status='success'
        ).exclude(id=login.id).order_by('-created_at').first()
        
        if last_login and last_login.country_code and login.country_code:
            if last_login.country_code != login.country_code:
                logger.warning(
                    f"Login from new country: {login.email} "
                    f"({last_login.country_code} -> {login.country_code})"
                )
                _queue_suspicious_login_alert(login)


def _handle_failed_login(login: LoginHistory):
    """Handle failed login attempt."""
    # Count recent failures
    recent_window = timezone.now() - timedelta(minutes=30)
    failure_count = LoginHistory.objects.filter(
        email=login.email,
        status='failed',
        created_at__gte=recent_window
    ).count()
    
    # Log warning thresholds
    if failure_count == 5:
        logger.warning(f"5 failed login attempts: {login.email} from {login.ip_address}")
    elif failure_count == 10:
        logger.error(f"10 failed login attempts: {login.email} from {login.ip_address}")
        _queue_brute_force_alert(login)
    
    # Track IP-based failures
    ip_failures = LoginHistory.objects.filter(
        ip_address=login.ip_address,
        status='failed',
        created_at__gte=recent_window
    ).count()
    
    if ip_failures >= 20:
        logger.error(f"Possible brute force from IP: {login.ip_address}")


def _handle_blocked_login(login: LoginHistory):
    """Handle blocked login attempt."""
    logger.warning(
        f"Login blocked: {login.email} from {login.ip_address} - "
        f"reason: {login.fail_reason}"
    )


# ==================== Async Task Queues ====================
# These functions queue Celery tasks for async processing

def _queue_welcome_email(user: User):
    """Queue welcome email for new verified user."""
    try:
        from .tasks import send_welcome_email
        transaction.on_commit(lambda: send_welcome_email.delay(str(user.id)))
        logger.debug(f"Queued welcome email for {user.email}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping welcome email")


def _queue_password_change_notification(user: User):
    """Queue password change notification."""
    try:
        from .tasks import send_password_change_notification
        transaction.on_commit(lambda: send_password_change_notification.delay(str(user.id)))
        logger.debug(f"Queued password change notification for {user.email}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping password notification")


def _queue_new_device_notification(session: UserSession):
    """Queue new device login notification."""
    try:
        from .tasks import send_new_device_notification
        transaction.on_commit(lambda: send_new_device_notification.delay(session.id))
        logger.debug(f"Queued new device notification for session {session.id}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping device notification")


def _queue_deletion_confirmation_email(request: AccountDeletionRequest):
    """Queue deletion confirmation email."""
    try:
        from .tasks import send_deletion_confirmation
        transaction.on_commit(lambda: send_deletion_confirmation.delay(request.id))
        logger.debug(f"Queued deletion confirmation for {request.user.email}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping deletion confirmation")


def _queue_suspicious_login_alert(login: LoginHistory):
    """Queue suspicious login alert."""
    try:
        from .tasks import send_suspicious_login_alert
        transaction.on_commit(lambda: send_suspicious_login_alert.delay(login.id))
        logger.debug(f"Queued suspicious login alert for {login.email}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping suspicious login alert")


def _queue_brute_force_alert(login: LoginHistory):
    """Queue brute force attack alert."""
    try:
        from .tasks import send_brute_force_alert
        transaction.on_commit(lambda: send_brute_force_alert.delay(login.email, login.ip_address))
        logger.debug(f"Queued brute force alert for {login.email}")
    except ImportError:
        logger.warning("Celery tasks not available, skipping brute force alert")
