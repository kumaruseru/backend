from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.notifications'
    verbose_name = _('Notifications')

    def ready(self):
        try:
            import apps.users.notifications.signals
        except ImportError:
            pass
