from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.analytics'
    verbose_name = _('Analytics')

    def ready(self):
        try:
            import apps.commerce.analytics.signals
        except ImportError:
            pass
