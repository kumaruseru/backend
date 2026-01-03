"""
Users Identity - Celery Tasks.

Production-ready async tasks for:
- Email notifications
- Security alerts
- Account management
- Session cleanup
"""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from datetime import timedelta

logger = logging.getLogger('apps.identity.tasks')


# ==================== Email Configuration ====================

DEFAULT_FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@owls.vn')
FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'https://owls.vn')


def send_html_email(subject: str, template_name: str, context: dict, to_email: str):
    """
    Send HTML email with plain text fallback.
    """
    try:
        html_content = render_to_string(f'emails/{template_name}.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()
        
        logger.info(f"Email sent: {subject} to {to_email}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send email to {to_email}: {e}")
        raise


# ==================== User Notification Tasks ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_id: str):
    """
    Send welcome email to newly verified user.
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'site_url': FRONTEND_URL,
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@owls.vn'),
        }
        
        send_html_email(
            subject='Chào mừng bạn đến với OWLS! 🦉',
            template_name='welcome',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        
    except User.DoesNotExist:
        logger.warning(f"User not found for welcome email: {user_id}")
    except Exception as e:
        logger.exception(f"Failed to send welcome email: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id: str):
    """
    Send email verification link to newly registered user.
    """
    try:
        from .models import User
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        user = User.objects.get(id=user_id)
        
        # Don't send if already verified
        if user.is_email_verified:
            return
        
        # Generate verification token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        verification_url = f"{FRONTEND_URL}/verify-email?uid={uid}&token={token}"
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'verification_url': verification_url,
            'site_url': FRONTEND_URL,
            'expires_hours': 24,
        }
        
        send_html_email(
            subject='Xác thực địa chỉ email của bạn ✉️',
            template_name='email_verification',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Verification email sent to {user.email}")
        
    except User.DoesNotExist:
        logger.warning(f"User not found for verification email: {user_id}")
    except Exception as e:
        logger.exception(f"Failed to send verification email: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_change_notification(self, user_id: str):
    """
    Notify user that password was changed.
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'changed_at': timezone.now().strftime('%H:%M %d/%m/%Y'),
            'site_url': FRONTEND_URL,
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@owls.vn'),
        }
        
        send_html_email(
            subject='Mật khẩu của bạn đã được thay đổi 🔐',
            template_name='password_changed',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Password change notification sent to {user.email}")
        
    except User.DoesNotExist:
        logger.warning(f"User not found for password notification: {user_id}")
    except Exception as e:
        logger.exception(f"Failed to send password notification: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_new_device_notification(self, session_id: int):
    """
    Notify user of login from new device.
    """
    try:
        from .models import UserSession
        session = UserSession.objects.select_related('user').get(id=session_id)
        user = session.user
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'device': session.device_name or session.device_type,
            'browser': session.browser,
            'os': session.os,
            'ip_address': session.ip_address,
            'location': session.location or 'Không xác định',
            'login_time': session.created_at.strftime('%H:%M %d/%m/%Y'),
            'site_url': FRONTEND_URL,
            'security_url': f"{FRONTEND_URL}/account/security",
        }
        
        send_html_email(
            subject='Đăng nhập từ thiết bị mới 📱',
            template_name='new_device_login',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"New device notification sent to {user.email}")
        
    except UserSession.DoesNotExist:
        logger.warning(f"Session not found: {session_id}")
    except Exception as e:
        logger.exception(f"Failed to send new device notification: {e}")
        raise self.retry(exc=e)


# ==================== Account Deletion Tasks ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_deletion_confirmation(self, request_id: int):
    """
    Send confirmation email for account deletion request.
    """
    try:
        from .models import AccountDeletionRequest
        request = AccountDeletionRequest.objects.select_related('user').get(id=request_id)
        user = request.user
        
        days_remaining = (request.scheduled_at - timezone.now()).days
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'scheduled_date': request.scheduled_at.strftime('%d/%m/%Y'),
            'days_remaining': days_remaining,
            'cancel_url': f"{FRONTEND_URL}/account/cancel-deletion",
            'site_url': FRONTEND_URL,
        }
        
        send_html_email(
            subject='Xác nhận yêu cầu xóa tài khoản ⚠️',
            template_name='deletion_confirmation',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Deletion confirmation sent to {user.email}")
        
    except AccountDeletionRequest.DoesNotExist:
        logger.warning(f"Deletion request not found: {request_id}")
    except Exception as e:
        logger.exception(f"Failed to send deletion confirmation: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1)
def send_deletion_reminders(self):
    """
    Send reminder emails for pending deletion requests.
    Runs daily via Celery Beat.
    """
    from .models import AccountDeletionRequest
    
    # Get requests scheduled in next 7 days
    week_from_now = timezone.now() + timedelta(days=7)
    
    pending = AccountDeletionRequest.objects.filter(
        status='pending',
        scheduled_at__lte=week_from_now,
        scheduled_at__gt=timezone.now()
    ).select_related('user')
    
    sent_count = 0
    for request in pending:
        days_remaining = (request.scheduled_at - timezone.now()).days
        
        # Send reminders at 7, 3, and 1 day(s) before
        if days_remaining in [7, 3, 1]:
            try:
                context = {
                    'user': request.user,
                    'first_name': request.user.first_name or 'bạn',
                    'days_remaining': days_remaining,
                    'scheduled_date': request.scheduled_at.strftime('%d/%m/%Y'),
                    'cancel_url': f"{FRONTEND_URL}/account/cancel-deletion",
                }
                
                send_html_email(
                    subject=f'Nhắc nhở: Tài khoản sẽ bị xóa trong {days_remaining} ngày',
                    template_name='deletion_reminder',
                    context=context,
                    to_email=request.user.email
                )
                sent_count += 1
            except Exception as e:
                logger.exception(f"Failed to send deletion reminder: {e}")
    
    logger.info(f"Sent {sent_count} deletion reminders")
    return sent_count


@shared_task(bind=True, max_retries=1)
def process_scheduled_deletions(self):
    """
    Process account deletions that have passed their scheduled date.
    Runs daily via Celery Beat.
    """
    from .models import AccountDeletionRequest
    
    # Get approved requests past scheduled date
    due_requests = AccountDeletionRequest.objects.filter(
        status__in=['pending', 'approved'],
        scheduled_at__lte=timezone.now()
    ).select_related('user')
    
    deleted_count = 0
    for request in due_requests:
        try:
            # Execute deletion
            request.execute()
            deleted_count += 1
            
            logger.info(f"Account deleted: {request.user.email}")
            
            # Send final confirmation
            send_deletion_complete_notification.delay(request.user.email)
            
        except Exception as e:
            logger.exception(f"Failed to delete account: {e}")
    
    logger.info(f"Processed {deleted_count} account deletions")
    return deleted_count


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_deletion_complete_notification(self, email: str):
    """
    Send final notification that account has been deleted.
    """
    try:
        context = {
            'email': email,
            'site_url': FRONTEND_URL,
        }
        
        send_html_email(
            subject='Tài khoản của bạn đã được xóa',
            template_name='deletion_complete',
            context=context,
            to_email=email
        )
        
    except Exception as e:
        logger.exception(f"Failed to send deletion complete notification: {e}")
        raise self.retry(exc=e)


# ==================== Security Alert Tasks ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_suspicious_login_alert(self, login_id: int):
    """
    Alert user of suspicious login activity.
    """
    try:
        from .models import LoginHistory
        login = LoginHistory.objects.select_related('user').get(id=login_id)
        
        if not login.user:
            return
        
        user = login.user
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'ip_address': login.ip_address,
            'location': login.location or 'Không xác định',
            'country': login.country_code or 'Không xác định',
            'device': login.device_type,
            'browser': login.browser,
            'login_time': login.created_at.strftime('%H:%M %d/%m/%Y'),
            'security_url': f"{FRONTEND_URL}/account/security",
            'password_reset_url': f"{FRONTEND_URL}/password/reset",
        }
        
        send_html_email(
            subject='Cảnh báo: Đăng nhập đáng ngờ được phát hiện ⚠️',
            template_name='suspicious_login',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Suspicious login alert sent to {user.email}")
        
    except LoginHistory.DoesNotExist:
        logger.warning(f"Login history not found: {login_id}")
    except Exception as e:
        logger.exception(f"Failed to send suspicious login alert: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_brute_force_alert(self, email: str, ip_address: str):
    """
    Alert user of potential brute force attack.
    """
    try:
        from .models import User
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.warning(f"User not found for brute force alert: {email}")
            return
        
        context = {
            'user': user,
            'first_name': user.first_name or 'bạn',
            'ip_address': ip_address,
            'attempt_time': timezone.now().strftime('%H:%M %d/%m/%Y'),
            'security_url': f"{FRONTEND_URL}/account/security",
            'password_reset_url': f"{FRONTEND_URL}/password/reset",
        }
        
        send_html_email(
            subject='Cảnh báo bảo mật: Nhiều lần đăng nhập thất bại 🚨',
            template_name='brute_force_alert',
            context=context,
            to_email=user.email
        )
        
        logger.info(f"Brute force alert sent to {user.email}")
        
        # Also notify admins
        _notify_admins_brute_force(email, ip_address)
        
    except Exception as e:
        logger.exception(f"Failed to send brute force alert: {e}")
        raise self.retry(exc=e)


def _notify_admins_brute_force(email: str, ip_address: str):
    """Notify admin users of brute force attempt."""
    admin_emails = getattr(settings, 'ADMINS', [])
    if not admin_emails:
        return
    
    admin_email_list = [email for name, email in admin_emails]
    
    try:
        send_mail(
            subject=f'[SECURITY] Brute force attempt: {email}',
            message=f'Multiple failed login attempts detected.\n\nEmail: {email}\nIP: {ip_address}\nTime: {timezone.now()}',
            from_email=DEFAULT_FROM_EMAIL,
            recipient_list=admin_email_list,
            fail_silently=True
        )
    except Exception as e:
        logger.exception(f"Failed to notify admins: {e}")


# ==================== Cleanup Tasks ====================

@shared_task(bind=True, max_retries=1)
def cleanup_expired_sessions(self):
    """
    Clean up expired user sessions.
    Runs hourly via Celery Beat.
    """
    from .models import UserSession
    
    # Mark expired sessions as inactive
    expired_count = UserSession.objects.filter(
        expires_at__lt=timezone.now(),
        is_active=True
    ).update(is_active=False)
    
    # Delete very old sessions (> 90 days)
    cutoff = timezone.now() - timedelta(days=90)
    deleted_count, _ = UserSession.objects.filter(
        created_at__lt=cutoff,
        is_active=False
    ).delete()
    
    logger.info(f"Session cleanup: {expired_count} expired, {deleted_count} deleted")
    return {'expired': expired_count, 'deleted': deleted_count}


@shared_task(bind=True, max_retries=1)
def cleanup_old_login_history(self):
    """
    Archive/delete old login history records.
    Runs weekly.
    """
    from .models import LoginHistory
    
    # Keep 6 months of history
    cutoff = timezone.now() - timedelta(days=180)
    
    deleted_count, _ = LoginHistory.objects.filter(
        created_at__lt=cutoff
    ).delete()
    
    logger.info(f"Login history cleanup: {deleted_count} records deleted")
    return deleted_count
