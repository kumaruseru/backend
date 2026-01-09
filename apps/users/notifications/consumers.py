"""Users Notifications - WebSocket Consumers for Real-time Notifications."""
import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

logger = logging.getLogger('apps.notifications')

User = get_user_model()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    Connect: ws://localhost:8000/ws/notifications/
    Authentication: JWT token in query string or via access_token message
    
    Client messages:
    - {"type": "authenticate", "token": "jwt_token"}
    - {"type": "mark_read", "notification_id": "uuid"}
    - {"type": "mark_all_read"}
    - {"type": "get_unread_count"}
    
    Server messages:
    - {"type": "notification", "data": {...}}
    - {"type": "unread_count", "count": 5}
    - {"type": "authenticated", "success": true}
    - {"type": "error", "message": "..."}
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_group_name = None
    
    async def connect(self):
        """Accept connection, authenticate later via message or query param."""
        await self.accept()
        
        # Try to get token from query string
        query_string = self.scope.get('query_string', b'').decode()
        if 'token=' in query_string:
            token = query_string.split('token=')[1].split('&')[0]
            await self._authenticate_with_token(token)
    
    async def disconnect(self, close_code):
        """Leave the user's notification group."""
        if self.user_group_name:
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
            logger.info(f"User {self.user.email} disconnected from notifications")
    
    async def receive_json(self, content):
        """Handle incoming messages from client."""
        message_type = content.get('type')
        
        if message_type == 'authenticate':
            await self._authenticate_with_token(content.get('token'))
        
        elif message_type == 'mark_read':
            if not self.user:
                await self.send_json({'type': 'error', 'message': 'Not authenticated'})
                return
            notification_id = content.get('notification_id')
            success = await self._mark_notification_read(notification_id)
            await self.send_json({'type': 'read_status', 'success': success, 'notification_id': notification_id})
            # Send updated unread count
            count = await self._get_unread_count()
            await self.send_json({'type': 'unread_count', 'count': count})
        
        elif message_type == 'mark_all_read':
            if not self.user:
                await self.send_json({'type': 'error', 'message': 'Not authenticated'})
                return
            count = await self._mark_all_read()
            await self.send_json({'type': 'all_read', 'marked_count': count})
            await self.send_json({'type': 'unread_count', 'count': 0})
        
        elif message_type == 'get_unread_count':
            if not self.user:
                await self.send_json({'type': 'error', 'message': 'Not authenticated'})
                return
            count = await self._get_unread_count()
            await self.send_json({'type': 'unread_count', 'count': count})
        
        elif message_type == 'ping':
            await self.send_json({'type': 'pong'})
        
        else:
            await self.send_json({'type': 'error', 'message': f'Unknown message type: {message_type}'})
    
    async def _authenticate_with_token(self, token: str):
        """Authenticate user with JWT token."""
        if not token:
            await self.send_json({'type': 'authenticated', 'success': False, 'error': 'No token provided'})
            return
        
        user = await self._verify_jwt_token(token)
        if user:
            self.user = user
            self.user_group_name = f'notifications_{user.id}'
            
            # Join user's notification group
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            
            await self.send_json({
                'type': 'authenticated',
                'success': True,
                'user_id': str(user.id),
                'email': user.email
            })
            
            # Send initial unread count
            count = await self._get_unread_count()
            await self.send_json({'type': 'unread_count', 'count': count})
            
            logger.info(f"User {user.email} authenticated for notifications WebSocket")
        else:
            await self.send_json({'type': 'authenticated', 'success': False, 'error': 'Invalid token'})
    
    @database_sync_to_async
    def _verify_jwt_token(self, token: str):
        """Verify JWT token and return user."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework_simplejwt.exceptions import TokenError
            
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            return User.objects.filter(id=user_id, is_active=True).first()
        except TokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT verification error: {e}")
            return None
    
    @database_sync_to_async
    def _get_unread_count(self) -> int:
        """Get unread notification count for user."""
        from .models import Notification
        return Notification.objects.filter(user=self.user, is_read=False).count()
    
    @database_sync_to_async
    def _mark_notification_read(self, notification_id: str) -> bool:
        """Mark a single notification as read."""
        from .models import Notification
        from django.utils import timezone
        try:
            updated = Notification.objects.filter(
                id=notification_id,
                user=self.user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
            return updated > 0
        except Exception:
            return False
    
    @database_sync_to_async
    def _mark_all_read(self) -> int:
        """Mark all notifications as read."""
        from .models import Notification
        from django.utils import timezone
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
    
    # ---- Group message handlers (called by channel layer) ----
    
    async def notification_new(self, event):
        """Send new notification to WebSocket client."""
        await self.send_json({
            'type': 'notification',
            'data': event['notification']
        })
    
    async def notification_count_update(self, event):
        """Send updated unread count."""
        await self.send_json({
            'type': 'unread_count',
            'count': event['count']
        })


# Helper function to push notification to WebSocket
async def push_notification_to_websocket(user_id: str, notification_data: dict):
    """
    Push a notification to user's WebSocket connection.
    
    Usage in services:
        from .consumers import push_notification_to_websocket
        from asgiref.sync import async_to_sync
        
        async_to_sync(push_notification_to_websocket)(
            str(user.id),
            {
                'id': str(notification.id),
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'action_url': notification.action_url,
                'created_at': notification.created_at.isoformat(),
            }
        )
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    group_name = f'notifications_{user_id}'
    
    await channel_layer.group_send(
        group_name,
        {
            'type': 'notification_new',
            'notification': notification_data
        }
    )
