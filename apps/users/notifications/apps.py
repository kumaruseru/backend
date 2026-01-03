"""Users Notifications App Configuration."""
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notification system app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.notifications'
    label = 'notifications'
    verbose_name = 'Notifications'
    
    def ready(self):
        """Import signals when app is ready."""
        from . import signals  # noqa: F401
