from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class MarketingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.marketing'
    verbose_name = _('Marketing')

    def ready(self):
        try:
            import apps.store.marketing.signals
        except ImportError:
            pass
