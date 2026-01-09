from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class IdentityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.identity'
    verbose_name = _('Identity')

    def ready(self):
        try:
            import apps.users.identity.signals
        except ImportError:
            pass
