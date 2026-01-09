from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class SocialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users.social'
    verbose_name = _('Social')

    def ready(self):
        try:
            import apps.users.social.signals
        except ImportError:
            pass
