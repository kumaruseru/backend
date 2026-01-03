"""Store Catalog App Configuration."""
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Product catalog app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store.catalog'
    label = 'catalog'
    verbose_name = 'Product Catalog'
