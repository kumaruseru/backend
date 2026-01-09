from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.orders'
    verbose_name = _('Orders')

    def ready(self):
        try:
            import apps.commerce.orders.signals
        except ImportError:
            pass
