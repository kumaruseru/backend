from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.security'
    verbose_name = _('Security')

    def ready(self):
        try:
            import apps.users.security.signals
        except ImportError:
            pass
