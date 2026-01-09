import logging
from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger('apps.notifications')
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_async(self, user_id: str, notification_type: str, context: dict, channels: list = None):
    from .services import NotificationService

    try:
        user = User.objects.get(id=user_id)
        NotificationService.send(
            user=user,
            notification_type=notification_type,
            context=context,
            channels=channels
        )
        logger.info(f"Notification sent to {user.email}: {notification_type}")
    except User.DoesNotExist:
        logger.warning(f"User {user_id} not found for notification")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def notify_admin_urgent(
    self,
    title: str,
    message: str,
    order_id: str = None,
    priority: str = 'high',
    **kwargs
):
    from .services import EmailService
    from django.conf import settings

    try:
        admin_emails = list(
            User.objects.filter(
                is_staff=True,
                is_active=True
            ).values_list('email', flat=True)
        )

        if not admin_emails:
            logger.warning("No admin users found for urgent notification")
            return

        priority_icons = {
            'low': 'ℹ️',
            'normal': '📋',
            'high': '⚠️',
            'urgent': '🚨'
        }
        icon = priority_icons.get(priority, '📋')
        subject = f"{icon} [{priority.upper()}] {title}"

        order_link = ''
        if order_id:
            order_link = f"<div style='padding: 15px; background: #fff;'><a href='{settings.FRONTEND_URL}/admin/orders/{order_id}' style='display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;'>Xem đơn hàng</a></div>"

        bg_color = '#dc3545' if priority in ['high', 'urgent'] else '#ffc107'
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {bg_color}; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">{icon} {title}</h1>
            </div>
            <div style="padding: 20px; background: #f8f9fa; border: 1px solid #dee2e6;">
                <pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">{message}</pre>
            </div>
            {order_link}
            <div style="padding: 10px; text-align: center; color: #6c757d; font-size: 12px;">
                Hệ thống thông báo tự động - Owls Admin
            </div>
        </div>
        """

        for email in admin_emails:
            try:
                EmailService._send_simple(
                    to_email=email,
                    subject=subject,
                    html_message=html_message
                )
                logger.info(f"Urgent notification sent to admin: {email}")
            except Exception as e:
                logger.error(f"Failed to send to {email}: {e}")

        logger.info(f"Urgent notification sent to {len(admin_emails)} admins: {title}")

    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        raise self.retry(exc=e)


@shared_task
def send_email_async(to_email: str, subject: str, html_message: str):
    from .services import EmailService

    try:
        EmailService._send_simple(to_email, subject, html_message)
        logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        raise


@shared_task
def cleanup_old_notifications(days: int = 90):
    from django.utils import timezone
    from datetime import timedelta
    from .models import Notification

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Notification.objects.filter(
        created_at__lt=cutoff,
        is_read=True
    ).delete()

    logger.info(f"Cleaned up {deleted} old notifications")
