from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ShippingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.shipping'
    verbose_name = _('Shipping')

    def ready(self):
        try:
            import apps.commerce.shipping.signals
        except ImportError:
            pass
