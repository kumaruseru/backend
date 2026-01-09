import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.db import models, transaction
from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationLog, NotificationType
)

logger = logging.getLogger('apps.notifications')

FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'https://owls.vn')
DEFAULT_FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@owls.vn')
FCM_API_KEY = getattr(settings, 'FCM_API_KEY', None)


class NotificationService:
    @staticmethod
    @transaction.atomic
    def send(
        user,
        notification_type: str,
        context: dict,
        channels: List[str] = None,
        priority: int = 1,
        data: dict = None,
        expires_at=None
    ) -> Notification:
        template = NotificationTemplate.objects.filter(
            notification_type=notification_type,
            is_active=True
        ).first()

        if template:
            rendered = template.render(context)
            title = rendered['title']
            message = rendered['message']
            action_url = rendered['action_url']
            action_text = rendered['action_text']
            default_channels = template.default_channels
        else:
            title = context.get('title', 'Thông báo')
            message = context.get('message', '')
            action_url = context.get('action_url', '')
            action_text = context.get('action_text', '')
            default_channels = ['in_app', 'email']

        channels = channels or default_channels
        enabled_channels = NotificationService._get_enabled_channels(
            user, notification_type, channels
        )

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            action_text=action_text,
            data=data or {},
            priority=priority,
            expires_at=expires_at,
            channels_sent=enabled_channels
        )

        # Deliver to each channel
        for channel in enabled_channels:
            NotificationService._deliver_to_channel(
                notification, channel, template, context
            )

        # Push to WebSocket for real-time delivery (in_app channel)
        if 'in_app' in enabled_channels:
            NotificationService._push_to_websocket(notification)

        logger.info(
            f"Notification sent: {notification_type} to {user.email} "
            f"via {enabled_channels}"
        )

        return notification

    @staticmethod
    def _get_enabled_channels(user, notification_type: str, requested_channels: list) -> list:
        pref = NotificationPreference.objects.filter(
            user=user,
            notification_type=notification_type
        ).first()

        enabled = []
        for channel in requested_channels:
            if pref:
                if channel == 'in_app' and pref.in_app_enabled:
                    enabled.append(channel)
                elif channel == 'email' and pref.email_enabled:
                    enabled.append(channel)
                elif channel == 'push' and pref.push_enabled:
                    enabled.append(channel)
                elif channel == 'sms' and pref.sms_enabled:
                    enabled.append(channel)
            else:
                if channel in ['in_app', 'email', 'push']:
                    enabled.append(channel)

        return enabled

    @staticmethod
    def _deliver_to_channel(
        notification: Notification,
        channel: str,
        template: NotificationTemplate,
        context: dict
    ):
        log = NotificationLog.objects.create(
            notification=notification,
            channel=channel
        )

        try:
            if channel == 'in_app':
                log.mark_delivered()
            elif channel == 'email':
                EmailService.send_notification_email(
                    notification, template, context, log
                )
            elif channel == 'push':
                PushService.send_push_notification(
                    notification, template, context, log
                )
            elif channel == 'sms':
                log.mark_failed("SMS not implemented")
        except Exception as e:
            log.mark_failed(str(e))
            logger.exception(f"Failed to deliver {channel}: {e}")

    @staticmethod
    def _push_to_websocket(notification):
        """Push notification to user's WebSocket connection for real-time delivery."""
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.debug("No channel layer configured, skipping WebSocket push")
                return
            
            group_name = f'notifications_{notification.user.id}'
            notification_data = {
                'id': str(notification.id),
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'image_url': notification.image_url,
                'data': notification.data,
                'priority': notification.priority,
                'created_at': notification.created_at.isoformat(),
            }
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_new',
                    'notification': notification_data
                }
            )
            logger.debug(f"WebSocket push sent to {notification.user.email}")
        except Exception as e:
            # Don't fail the whole notification if WebSocket push fails
            logger.warning(f"WebSocket push failed: {e}")

    @staticmethod
    def get_user_notifications(
        user,
        unread_only: bool = False,
        notification_type: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        queryset = Notification.objects.filter(user=user)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) |
            models.Q(expires_at__gt=timezone.now())
        )

        total = queryset.count()
        notifications = list(queryset.order_by('-created_at')[offset:offset + limit])
        unread_count = Notification.objects.filter(user=user, is_read=False).count()

        return {
            'notifications': notifications,
            'total': total,
            'unread_count': unread_count
        }

    @staticmethod
    def mark_as_read(notification_id: UUID, user) -> bool:
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user) -> int:
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

    @staticmethod
    def delete_notification(notification_id: UUID, user) -> bool:
        deleted, _ = Notification.objects.filter(
            id=notification_id,
            user=user
        ).delete()
        return deleted > 0

    @staticmethod
    def get_unread_count(user) -> int:
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def get_preferences(user) -> Dict[str, Dict]:
        prefs = NotificationPreference.objects.filter(user=user)
        pref_dict = {p.notification_type: p for p in prefs}

        result = {}
        for ntype, label in NotificationType.choices:
            if ntype in pref_dict:
                pref = pref_dict[ntype]
                result[ntype] = {
                    'label': label,
                    'in_app': pref.in_app_enabled,
                    'email': pref.email_enabled,
                    'push': pref.push_enabled,
                    'sms': pref.sms_enabled,
                }
            else:
                result[ntype] = {
                    'label': label,
                    'in_app': True,
                    'email': True,
                    'push': True,
                    'sms': False,
                }

        return result

    @staticmethod
    def update_preference(
        user,
        notification_type: str,
        in_app: bool = None,
        email: bool = None,
        push: bool = None,
        sms: bool = None
    ) -> NotificationPreference:
        pref, _ = NotificationPreference.objects.get_or_create(
            user=user,
            notification_type=notification_type
        )

        if in_app is not None:
            pref.in_app_enabled = in_app
        if email is not None:
            pref.email_enabled = email
        if push is not None:
            pref.push_enabled = push
        if sms is not None:
            pref.sms_enabled = sms

        pref.save()
        return pref

    @staticmethod
    def register_device(
        user,
        token: str,
        platform: str,
        device_name: str = ''
    ) -> DeviceToken:
        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'platform': platform,
                'device_name': device_name,
                'is_active': True
            }
        )
        logger.info(f"Device registered: {platform} for {user.email}")
        return device

    @staticmethod
    def unregister_device(token: str) -> bool:
        updated = DeviceToken.objects.filter(token=token).update(is_active=False)
        return updated > 0


class EmailService:
    @staticmethod
    def send_notification_email(
        notification: Notification,
        template: NotificationTemplate,
        context: dict,
        log: NotificationLog
    ):
        user = notification.user

        email_context = {
            **context,
            'user': user,
            'first_name': user.first_name or 'bạn',
            'notification': notification,
            'site_url': FRONTEND_URL,
            'action_url': notification.action_url,
            'unsubscribe_url': f"{FRONTEND_URL}/account/notifications",
        }

        if template and template.email_subject_template:
            subject = template.email_subject_template.format(**context)
        else:
            subject = notification.title

        if template and template.email_template_name:
            try:
                html_content = render_to_string(
                    f'emails/{template.email_template_name}.html',
                    email_context
                )
            except Exception:
                html_content = EmailService._default_email_template(notification, email_context)
        else:
            html_content = EmailService._default_email_template(notification, email_context)

        try:
            text_content = strip_tags(html_content)
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            email.attach_alternative(html_content, 'text/html')
            email.send()
            log.mark_sent()
            logger.info(f"Email sent to {user.email}: {subject}")
        except Exception as e:
            log.mark_failed(str(e))
            raise

    @staticmethod
    def _default_email_template(notification: Notification, context: dict) -> str:
        action_html = ''
        if notification.action_url:
            action_html = f'<p><a href="{notification.action_url}" class="button">{notification.action_text or "Xem chi tiết"}</a></p>'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #007bff; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
                .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>OWLS Store</h1>
                </div>
                <div class="content">
                    <h2>{notification.title}</h2>
                    <p>{notification.message}</p>
                    {action_html}
                </div>
                <div class="footer">
                    <p>OWLS Store - Cửa hàng thông minh</p>
                    <p><a href="{FRONTEND_URL}/account/notifications">Quản lý thông báo</a></p>
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def send_verification_email(user, verification_link: str) -> bool:
        return EmailService._send_simple(
            user.email,
            'Xác thực tài khoản OWLS Store',
            f"""
            <h2>Xin chào {user.first_name or user.email},</h2>
            <p>Cảm ơn bạn đã đăng ký tài khoản tại OWLS Store.</p>
            <p>Vui lòng click vào link bên dưới để xác thực email:</p>
            <p><a href="{verification_link}">Xác thực email</a></p>
            <p>Link này có hiệu lực trong 24 giờ.</p>
            <br>
            <p>Trân trọng,<br>OWLS Store Team</p>
            """
        )

    @staticmethod
    def send_password_reset_email(user, reset_link: str) -> bool:
        return EmailService._send_simple(
            user.email,
            'Đặt lại mật khẩu OWLS Store',
            f"""
            <h2>Xin chào {user.first_name or user.email},</h2>
            <p>Bạn đã yêu cầu đặt lại mật khẩu.</p>
            <p>Vui lòng click vào link bên dưới để tạo mật khẩu mới:</p>
            <p><a href="{reset_link}">Đặt lại mật khẩu</a></p>
            <p>Link này có hiệu lực trong 1 giờ.</p>
            <p>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.</p>
            <br>
            <p>Trân trọng,<br>OWLS Store Team</p>
            """
        )

    @staticmethod
    def send_order_confirmation(order) -> bool:
        items_html = ''
        for item in order.items.all():
            items_html += f'<tr><td>{item.product_name}</td><td>{item.quantity}</td><td>{item.subtotal:,.0f}₫</td></tr>'

        return EmailService._send_simple(
            order.user.email,
            f'Xác nhận đơn hàng #{order.order_number}',
            f"""
            <h2>Cảm ơn bạn đã đặt hàng!</h2>
            <p>Đơn hàng của bạn đã được tiếp nhận.</p>

            <h3>Thông tin đơn hàng #{order.order_number}</h3>
            <table border="1" cellpadding="10">
                <tr><th>Sản phẩm</th><th>Số lượng</th><th>Thành tiền</th></tr>
                {items_html}
            </table>

            <p><strong>Tạm tính:</strong> {order.subtotal:,.0f}₫</p>
            <p><strong>Phí ship:</strong> {order.shipping_fee:,.0f}₫</p>
            <p><strong>Tổng cộng:</strong> {order.total:,.0f}₫</p>

            <h3>Địa chỉ giao hàng</h3>
            <p>{order.recipient_name}<br>
            {order.phone}<br>
            {order.full_address}</p>

            <br>
            <p>Trân trọng,<br>OWLS Store Team</p>
            """
        )

    @staticmethod
    def _send_simple(to_email: str, subject: str, html_message: str) -> bool:
        try:
            plain_message = strip_tags(html_message)
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False


class PushService:
    @staticmethod
    def send_push_notification(
        notification: Notification,
        template: NotificationTemplate,
        context: dict,
        log: NotificationLog
    ):
        user = notification.user
        tokens = DeviceToken.objects.filter(
            user=user,
            is_active=True
        ).values_list('token', flat=True)

        if not tokens:
            log.mark_failed("No active device tokens")
            return

        if template:
            title = template.push_title_template.format(**context) if template.push_title_template else notification.title
            body = template.push_body_template.format(**context) if template.push_body_template else notification.message[:200]
        else:
            title = notification.title
            body = notification.message[:200]

        try:
            PushService._send_fcm(
                list(tokens),
                title,
                body,
                {
                    'notification_id': str(notification.id),
                    'type': notification.notification_type,
                    'action_url': notification.action_url,
                }
            )
            log.mark_sent()
            logger.info(f"Push sent to {len(tokens)} devices: {title}")
        except Exception as e:
            log.mark_failed(str(e))
            raise

    @staticmethod
    def _send_fcm(tokens: list, title: str, body: str, data: dict = None):
        if not FCM_API_KEY:
            raise Exception("FCM_API_KEY not configured")

        import requests

        headers = {
            'Authorization': f'key={FCM_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'registration_ids': tokens,
            'notification': {
                'title': title,
                'body': body,
                'sound': 'default'
            },
            'data': data or {}
        }

        response = requests.post(
            'https://fcm.googleapis.com/fcm/send',
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"FCM error: {response.text}")

        result = response.json()
        if result.get('failure', 0) > 0:
            logger.warning(f"FCM partial failure: {result}")
