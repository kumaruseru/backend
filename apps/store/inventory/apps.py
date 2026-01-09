from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.inventory'
    verbose_name = _('Inventory')

    def ready(self):
        try:
            import apps.store.inventory.signals
        except ImportError:
            pass
