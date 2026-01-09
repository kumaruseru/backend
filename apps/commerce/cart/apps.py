from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.cart'
    verbose_name = _('Cart')

    def ready(self):
        try:
            import apps.commerce.cart.signals
        except ImportError:
            pass
