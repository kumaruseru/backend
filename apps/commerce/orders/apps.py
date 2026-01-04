"""Commerce Orders App Configuration."""
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce.orders'
    label = 'orders'
    verbose_name = 'Order Management'
    
    def ready(self):
        """Register signal receivers."""
        from . import receivers  # noqa: F401

