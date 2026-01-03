"""Store Inventory App Configuration."""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Inventory management app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.inventory'
    label = 'inventory'
    verbose_name = 'Inventory Management'
